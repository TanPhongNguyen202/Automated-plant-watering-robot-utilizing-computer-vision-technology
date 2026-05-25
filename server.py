"""
Robot Web Server Module
Provides REST API for remote control and status monitoring of the robot.
"""

from flask import Flask, render_template, Response, jsonify, request
from datetime import datetime
import cv2
from queue import Empty
import threading
import os
from functools import wraps

from src.robot.modes import Modes
from src.utils.logger import Logger
from src.utils.control_utils import direction

# ============= Configuration (from Environment Variables) =============
# These can be overridden by setting environment variables
# Examples:
#   export ROBOT_SERVER_HOST="192.168.1.100"
#   export ROBOT_SERVER_PORT="8080"
#   export ROBOT_DEBUG_MODE="True"
#   export ROBOT_API_TOKEN="super_secret_token"
SERVER_HOST = os.getenv('ROBOT_SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('ROBOT_SERVER_PORT', 5000))
DEBUG_MODE = os.getenv('ROBOT_DEBUG_MODE', 'False').lower() == 'true'

# Security: Token-based authentication (set via environment variable)
# None = no authentication (development only - NOT recommended for production!)
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

# ============= Authentication Decorator =============
def require_auth(f):
    """Decorator to require API token authentication via Authorization header.
    
    Usage on routes:
        @app.route('/protected')
        @require_auth
        def protected_route():
            return jsonify({"status": "authorized"})
    
    Client must send:
        Authorization: Bearer <token>
    
    If ROBOT_API_TOKEN is not set (None), authentication is DISABLED (development mode).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If no token is set in environment, disable auth (development mode)
        if API_TOKEN is None:
            return f(*args, **kwargs)
        
        # Check for Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        # Extract token from "Bearer <token>" format
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate token (simple string comparison; production should use JWT)
        if token != API_TOKEN:
            return jsonify({"error": "Invalid API token"}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

try:
    frame_queue = robot.frame_queue
except AttributeError:
    logger.log_error("Robot frame queue not available")
    frame_queue = None


def generate_video_frames(mode: str) -> bytes:
    """
    Generate video frames for streaming.
    
    Args:
        mode: Frame type ('color' or 'object')
    
    Yields:
        JPEG encoded frame bytes
    """
    if frame_queue is None:
        logger.log_warning("Frame queue unavailable for video streaming")
        return
    
    frame_index = FRAME_INDICES.get(mode)
    if frame_index is None:
        logger.log_error(f"Unknown frame mode: {mode}")
        return
    
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
        
        except Empty:
            continue
        except Exception as e:
            logger.log_error(f"Error in video frame generation: {e}")
            break


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
    """
    Set robot operating mode.
    
    JSON payload: {"mode": "manual" or "automatic"}
    
    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        mode_value = data.get("mode", "").lower()
        valid_modes = {"manual", "automatic"}
        
        if mode_value not in valid_modes:
            return jsonify({"error": f"Invalid mode. Must be one of {valid_modes}"}), 400
        
        robot.switch_mode(mode_value)
        logger.log_info(f"Mode switched to: {mode_value}")
        
        return jsonify({"success": True, "mode": mode_value})
    
    except Exception as e:
        logger.log_error(f"Error setting mode: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/auto-command', methods=['POST'])
@require_auth
def auto_command() -> tuple:
    """
    Configure and start automatic mode.
    
    JSON payload: {
        "value1": mission_type (int),
        "startTime": "HH:MM",
        "endTime": "HH:MM"
    }
    
    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Validate and extract parameters
        mission = data.get("value1", 0)
        start_time_str = data.get("startTime")
        end_time_str = data.get("endTime")
        
        if not start_time_str or not end_time_str:
            return jsonify({"error": "Missing startTime or endTime"}), 400
        
        try:
            robot.daily_mission = int(mission)
            robot.OPERATION_START_TIME = datetime.strptime(start_time_str, 
                                                           '%H:%M').time()
            robot.OPERATION_END_TIME = datetime.strptime(end_time_str, 
                                                         '%H:%M').time()
        except ValueError as e:
            return jsonify({"error": f"Invalid time format: {e}"}), 400
        
        robot.switch_mode("automatic")
        
        # Start automatic mode in a background thread (non-blocking)
        # This prevents the Flask route from blocking the entire server
        mission_thread = threading.Thread(
            target=robot.automatic_mode,
            daemon=True,
            name="RobotAutomaticModeThread"
        )
        mission_thread.start()
        
        logger.log_info(f"Auto mission started: {start_time_str} - {end_time_str}")
        return jsonify({"success": True, "mission": mission})
    
    except Exception as e:
        logger.log_error(f"Error in auto command: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/status', methods=['GET'])
@require_auth
def get_status() -> tuple:
    """
    Get current robot status.
    
    Returns:
        JSON with battery, sensor, and motor status
    """
    try:
        battery_status = robot.battery.read_battery_status()
        front_distance = robot.ultrasonic_sensors.get_distance("front")
        left_distance = robot.ultrasonic_sensors.get_distance("left")
        right_distance = robot.ultrasonic_sensors.get_distance("right")
        
        status_data = {
            "voltage": battery_status[0],
            "current": battery_status[1],
            "power": battery_status[2],
            "battery_level": battery_status[3],
            "remaining_time": battery_status[4],
            "water_status": "Available" if robot.is_watering else "Empty",
            "wheel_speed": robot.vx,
            "front_sensor": front_distance,
            "left_sensor": left_distance,
            "right_sensor": right_distance,
            "robot_direction": robot.direction,
            "servo_bottom": robot.bottom_angle,
            "servo_top": robot.top_angle
        }
        
        return jsonify(status_data)
    
    except Exception as e:
        logger.log_error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/control', methods=['POST'])
@require_auth
def manual_control() -> tuple:
    """
    Handle manual control commands.
    
    JSON payload: {"command": "w/a/s/d/q/e/z/x/r/+/-/1/2/3"}
    
    Returns:
        JSON response with command status
    """
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
        
        # Handle speed control
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
        
        # Handle movement commands
        elif command in direction:
            move_direction = direction[command]
            robot.set_motors_direction(move_direction, robot.vx, robot.vy, 
                                      robot.theta)
            state_msg = f"Moving: {move_direction}"
        
        # Handle water pump
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


@app.errorhandler(404)
def not_found(error) -> tuple:
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error) -> tuple:
    """Handle 500 errors."""
    logger.log_error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    logger.log_info(f"Starting robot server on {SERVER_HOST}:{SERVER_PORT}")
    
    # Log security status
    if API_TOKEN is None:
        logger.log_error("⚠️  WARNING: API authentication DISABLED! Set ROBOT_API_TOKEN to enable.")
        logger.log_error("   Anyone on the network can control the robot!")
    else:
        logger.log_info("✓ API authentication ENABLED")
    
    # Log debug mode status
    if DEBUG_MODE:
        logger.log_error("⚠️  WARNING: DEBUG MODE ENABLED! Do not use in production!")
    
    # Start Flask app with threading support for non-blocking routes
    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=DEBUG_MODE,
        threaded=True
    )
