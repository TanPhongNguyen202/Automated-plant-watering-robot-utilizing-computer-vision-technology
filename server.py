"""
Robot Web Server Module
Provides Secure REST API for remote control and status monitoring of the robot.
Combines V2's security/environment config with V1's ironclad thread safety.
"""

import threading
from flask import Flask, render_template, Response, jsonify, request
from datetime import datetime
import cv2
from queue import Empty
import os
from functools import wraps

from src.robot.modes import Modes
from src.utils.logger import Logger
from src.utils.control_utils import direction

# ============= Configuration (from Environment Variables) =============
SERVER_HOST = os.getenv('ROBOT_SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('ROBOT_SERVER_PORT', 5000))
DEBUG_MODE = os.getenv('ROBOT_DEBUG_MODE', 'False').lower() == 'true'

# Security: Token-based authentication
API_TOKEN = os.getenv('ROBOT_API_TOKEN', None)
MAX_SPEED_LEVEL = 10
MIN_SPEED_LEVEL = 0
FRAME_INDICES = {
    'color': 1,
    'object': 18
}

# ============= Initialize Flask App =============
app = Flask(__name__)
robot = Modes()
logger = Logger()

# FIX V3: Khôi phục Lock và biến track luồng bảo vệ trạng thái robot tuyệt đối
robot_lock = threading.Lock()
_auto_thread: threading.Thread | None = None

try:
    frame_queue = robot.frame_queue
except AttributeError:
    logger.log_error("Robot frame queue not available")
    frame_queue = None


# ============= Authentication Decorator =============
def require_auth(f):
    """Decorator to require API token authentication via Authorization header."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if API_TOKEN is None:
            return f(*args, **kwargs)
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        if token != API_TOKEN:
            return jsonify({"error": "Invalid API token"}), 403
        
        return f(*args, **kwargs)
    return decorated_function


# ============= Video Streaming =============
def generate_video_frames(mode: str):
    """
    Generate video frames for streaming.
    
    Đã cải tiến: Tự phục hồi khi lỗi thoáng qua, nhưng ngắt stream an toàn 
    nếu lỗi liên tiếp vượt ngưỡng (tránh tràn tài nguyên khi mất camera hẳn).
    """
    if frame_queue is None:
        logger.log_warning("Frame queue unavailable for video streaming")
        return
    
    frame_index = FRAME_INDICES.get(mode)
    if frame_index is None:
        logger.log_error(f"Unknown frame mode: {mode}")
        return
    
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 10

    while True:
        try:
            frame_data = frame_queue.get(timeout=1)
            if frame_data and len(frame_data) > frame_index:
                output_frame = frame_data[frame_index]
                if output_frame is not None:
                    _, buffer = cv2.imencode('.jpg', output_frame)
                    frame_bytes = (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + 
                                   buffer.tobytes() + b'\r\n')
                    yield frame_bytes
                    consecutive_errors = 0  # Reset counter khi thành công
        except Empty:
            continue
        except Exception as e:
            consecutive_errors += 1
            logger.log_error(f"Error in video frame generation: {e} (#{consecutive_errors})")
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.log_error("Too many consecutive errors, stopping stream safely")
                break
            continue


# ============= Routes =============
@app.route('/')
def index() -> str:
    """Serve the main HTML interface."""
    logger.log_info("Main page accessed")
    return render_template('index.html')


@app.route('/video_feed/color')
def video_feed_color() -> Response:
    """Stream color detection video feed."""
    logger.log_info("Color video stream started")
    return Response(generate_video_frames('color'),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed/object')
def video_feed_object() -> Response:
    """Stream object detection video feed."""
    logger.log_info("Object video stream started")
    return Response(generate_video_frames('object'),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/mode', methods=['POST'])
@require_auth
def set_mode() -> tuple:
    """Set robot operating mode."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        mode_value = data.get("mode", "").lower()
        valid_modes = {"manual", "automatic"}
        if mode_value not in valid_modes:
            return jsonify({"error": f"Invalid mode. Must be one of {valid_modes}"}), 400
        
        # FIX V3: Đưa Lock bảo vệ trở lại khi can thiệp ghi trạng thái robot
        with robot_lock:
            robot.switch_mode(mode_value)
            
        logger.log_info(f"Mode switched to: {mode_value}")
        return jsonify({"success": True, "mode": mode_value})
    except Exception as e:
        logger.log_error(f"Error setting mode: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/auto-command', methods=['POST'])
@require_auth
def auto_command() -> tuple:
    """Configure and start automatic mode in background thread."""
    global _auto_thread
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        mission = data.get("value1", 0)
        start_time_str = data.get("startTime")
        end_time_str = data.get("endTime")
        
        if not start_time_str or not end_time_str:
            return jsonify({"error": "Missing startTime or endTime"}), 400
        
        # FIX V3: Lock khi cấu hình các thông số nhiệm vụ phần cứng
        with robot_lock:
            try:
                robot.daily_mission = int(mission)
                robot.OPERATION_START_TIME = datetime.strptime(start_time_str, '%H:%M').time()
                robot.OPERATION_END_TIME = datetime.strptime(end_time_str, '%H:%M').time()
            except ValueError as e:
                return jsonify({"error": f"Invalid time format: {e}"}), 400
            
            robot.switch_mode("automatic")
        
        # FIX V3: Kiểm tra và ngăn chặn đẻ vô hạn thread đè lệnh phần cứng
        if _auto_thread is not None and _auto_thread.is_alive():
            return jsonify({
                "error": "Automatic mode is already running. Stop it first before starting a new mission."
            }), 409

        _auto_thread = threading.Thread(
            target=robot.automatic_mode,
            daemon=True,
            name="RobotAutomaticModeThread"
        )
        _auto_thread.start()
        
        logger.log_info(f"Auto mission started: {start_time_str} - {end_time_str}")
        return jsonify({"success": True, "mission": mission})
    except Exception as e:
        logger.log_error(f"Error in auto command: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/status', methods=['GET'])
@require_auth
def get_status() -> tuple:
    """Get current robot status với cơ chế bảo vệ thread-safe cô lập."""
    try:
        # FIX V3: Lock toàn bộ quá trình đọc để tránh race-condition với luồng điều khiển
        with robot_lock:
            # Đọc cảm biến riêng lẻ (cô lập ngoại lệ bằng try-except con như V1)
            try:
                battery_status = robot.battery.read_battery_status() if getattr(robot, 'battery', None) else None
                voltage, current, power, battery_level, remaining_time = battery_status if battery_status else (0, 0, 0, 0, "N/A")
            except Exception as e:
                logger.log_warning(f"Failed to read battery status: {e}")
                voltage = current = power = battery_level = 0
                remaining_time = "N/A"
            
            try:
                front_distance = robot.ultrasonic_sensors.get_distance("front") if getattr(robot, 'ultrasonic_sensors', None) else 0
                left_distance = robot.ultrasonic_sensors.get_distance("left") if getattr(robot, 'ultrasonic_sensors', None) else 0
                right_distance = robot.ultrasonic_sensors.get_distance("right") if getattr(robot, 'ultrasonic_sensors', None) else 0
            except Exception as e:
                logger.log_warning(f"Failed to read ultrasonic sensors: {e}")
                front_distance = left_distance = right_distance = 0
                
            status_data = {
                "voltage": voltage,
                "current": current,
                "power": power,
                "battery_level": battery_level,
                "remaining_time": remaining_time,
                "water_status": "Available" if getattr(robot, 'is_watering', False) else "Empty",
                "wheel_speed": getattr(robot, 'vx', 0),
                "front_sensor": front_distance,
                "left_sensor": left_distance,
                "right_sensor": right_distance,
                "robot_direction": getattr(robot, 'direction', 'Unknown'),
                "servo_bottom": getattr(robot, 'bottom_angle', 0),
                "servo_top": getattr(robot, 'top_angle', 0),
                "auto_thread_alive": _auto_thread.is_alive() if _auto_thread else False
            }
            
        return jsonify(status_data)
    except Exception as e:
        logger.log_error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/control', methods=['POST'])
@require_auth
def manual_control() -> tuple:
    """Handle manual control commands."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        command = str(data.get('command', '')).strip()
        if not command:
            return jsonify({"error": "No command provided"}), 400
        
        valid_commands = set(direction.keys()) | {'+', '=', '-', '_', 'r', 'p'}
        if command not in valid_commands:
            return jsonify({"error": f"Invalid command: {command}"}), 400
        
        with robot_lock:
            if command in ['+', '=']:
                robot.n = min(robot.n + 1, MAX_SPEED_LEVEL)
                robot.vx = robot.n * robot.speed
                robot.vy = robot.n * robot.speed
                state_msg = f"Speed increased to {robot.n * 10}%"
            
            elif command in ['-', '_']:
                robot.n = max(robot.n - 1, MIN_SPEED_LEVEL)
                robot.vx = robot.n * robot.speed
                robot.vy = robot.n * robot.speed
                state_msg = f"Speed decreased to {robot.n * 10}%"
            
            elif command in direction:
                move_direction = direction[command]
                robot.set_motors_direction(move_direction, robot.vx, robot.vy, robot.theta)
                state_msg = f"Moving: {move_direction}"
            
            elif command == 'r':
                robot.relay_control.run_relay_for_duration()
                state_msg = "Watering activated"
            
            else:
                state_msg = "Command executed"
            
            robot.update_state(state_msg)
            
        logger.log_info(f"Command executed: {command}")
        return jsonify({"status": "success", "message": state_msg})
    except Exception as e:
        logger.log_error(f"Error in manual control: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/auto-status', methods=['GET'])
def auto_status() -> tuple:
    """Kiểm tra trạng thái auto thread."""
    return jsonify({
        "running": _auto_thread.is_alive() if _auto_thread else False
    })


@app.errorhandler(404)
def not_found(error) -> tuple:
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error) -> tuple:
    logger.log_error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    logger.log_info(f"Starting robot server on {SERVER_HOST}:{SERVER_PORT}")
    
    if API_TOKEN is None:
        logger.log_error("⚠️  WARNING: API authentication DISABLED! Set ROBOT_API_TOKEN to enable.")
    else:
        logger.log_info("✓ API authentication ENABLED")
        
    if DEBUG_MODE:
        logger.log_error("⚠️  WARNING: DEBUG MODE ENABLED! Do not use in production!")
    
    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=DEBUG_MODE,
        threaded=True
    )