"""
Motor Control and Input Management Utilities
Handles keyboard input, motor direction control, and object search algorithms.
"""

import sys
import tty
import termios
from time import sleep
from typing import Optional, Tuple, Dict
from queue import Empty

from src.hardware.motors import Motors
from src.hardware.kinematic import Kinematic
from src.utils.logger import Logger

# ============= Keyboard Command Mapping =============
direction: Dict[str, str] = {
    'w': "go_forward",
    's': "go_backward",
    'a': "go_left",
    'd': "go_right",
    'q': "diagonal_up_left",
    'e': "diagonal_up_right",
    'z': "diagonal_down_left",
    'x': "diagonal_down_right",
    '1': "stop",
    '2': "rotate_left",
    '3': "rotate_right"
}

# ============= Global Robot Instance =============
_robot_instance = Kinematic(0, 0, 0, 0)
_logger = Logger()


def getch() -> str:
    """
    Read a single character from stdin without echoing.
    
    Returns:
        Single character read from stdin
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        command = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return command


def set_motors_direction(command: str, vx: float, vy: float, 
                        theta: float) -> None:
    """
    Set motor speeds based on command direction.
    
    Args:
        command: Direction command from direction map
        vx: Velocity in x-axis
        vy: Velocity in y-axis
        theta: Rotation angle
    
    Raises:
        ValueError: If command is not valid
    """
    if command not in direction.values() and command != 'stop':
        raise ValueError(f"Invalid command: {command}")
    
    # Set kinematic parameters based on command
    command_map = {
        'go_forward': (vx, 0, theta, 0),
        'go_backward': (-vx, 0, theta, 0),
        'go_left': (0, vy, theta, 0),
        'go_right': (0, -vy, theta, 0),
        'diagonal_up_left': (vx, vy, theta, 0),
        'diagonal_down_left': (-vx, vy, theta, 0),
        'diagonal_up_right': (vx, -vy, theta, 0),
        'diagonal_down_right': (-vx, -vy, theta, 0),
        'stop': (0, 0, 0, 0),
        'rotate_left': (-vx, 0, theta, 1),
        'rotate_right': (vx, 0, theta, 1),
    }
    
    vxg, vyg, theta_d, turn = command_map.get(command, (0, 0, 0, 0))
    _robot_instance.vxg = vxg
    _robot_instance.vyg = vyg
    _robot_instance.theta_d = theta_d
    _robot_instance.turn = turn
    
    try:
        _robot_instance.backward_kinematics()
        
        motor_controller = Motors()
        
        # Clamp motor speeds between 0 and 1
        motor_speeds = [
            max(0, min(abs(_robot_instance.v1), 1)),
            max(0, min(abs(_robot_instance.v2), 1)),
            max(0, min(abs(_robot_instance.v3), 1)),
            max(0, min(abs(_robot_instance.v4), 1)),
        ]
        
        for i, speed in enumerate(motor_speeds, 1):
            motor_controller.set_speed(f"motor_{i}", speed)
        
        _logger.log_info(f"Motor speeds set: {motor_speeds}")
    
    except Exception as e:
        _logger.log_error(f"Error setting motor direction: {e}")


def search_for_object(servo_top, servo_bottom, frame_queue, num_turns: int = 4, 
                     step_angle: int = 30, start_angle_horizontal: int = 0, 
                     start_angle_vertical: int = 60) -> Optional[Tuple[int, int]]:
    """
    Search for an object by rotating servos and checking frame queue.
    
    Args:
        servo_top: Servo controlling horizontal rotation
        servo_bottom: Servo controlling vertical rotation
        frame_queue: Queue containing frame detection data
        num_turns: Number of search turns to perform
        step_angle: Angle step between servo movements (degrees)
        start_angle_horizontal: Initial horizontal servo angle
        start_angle_vertical: Initial vertical servo angle
    
    Returns:
        Tuple of (horizontal_angle, vertical_angle) if object found, else None
    
    Raises:
        ValueError: If angles exceed valid range
    """
    MAX_ANGLE = 120
    MIN_ANGLE = 0
    DEFAULT_VERTICAL_ANGLE = 80
    MAX_SEARCH_ITERATIONS = 2
    
    if not (MIN_ANGLE <= start_angle_horizontal <= MAX_ANGLE):
        raise ValueError(f"Invalid horizontal angle: {start_angle_horizontal}")
    if not (MIN_ANGLE <= start_angle_vertical <= MAX_ANGLE):
        raise ValueError(f"Invalid vertical angle: {start_angle_vertical}")
    
    current_horizontal = start_angle_horizontal
    current_vertical = start_angle_vertical
    
    _logger.log_info(f"Starting object search with {num_turns} turns")
    
    for iteration in range(MAX_SEARCH_ITERATIONS):
        for turn in range(num_turns):
            _logger.log_info(f"Search iteration {iteration + 1}/{MAX_SEARCH_ITERATIONS}, "
                           f"turn {turn + 1}/{num_turns}, angle: {current_horizontal}°")
            
            # Move servos to current angle
            servo_top.move_to_angle(current_horizontal)
            servo_bottom.move_to_angle(current_vertical)
            sleep(1)  # Wait for servo to stabilize
            
            # Check for object detection
            try:
                if not frame_queue.empty():
                    frame_data = frame_queue.get(timeout=0.5)
                    if frame_data and frame_data[0]:  # Check detection status
                        _logger.log_info(f"Object detected at angles: "
                                       f"H={current_horizontal}°, V={current_vertical}°")
                        return current_horizontal, current_vertical
            
            except Empty:
                pass
            except Exception as e:
                _logger.log_warning(f"Error checking frame queue: {e}")
            
            # Update angle for next iteration
            current_horizontal += step_angle
            
            # Reset to min angle if exceeded max
            if current_horizontal > MAX_ANGLE:
                current_horizontal = MIN_ANGLE
        
        # Reset servos after each iteration
        servo_bottom.move_to_angle(DEFAULT_VERTICAL_ANGLE)
        servo_top.move_to_angle(MIN_ANGLE)
    
    _logger.log_info("Object not found during search")
    return None
