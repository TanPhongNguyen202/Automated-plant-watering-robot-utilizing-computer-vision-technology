"""
Control Modules
PID control, line following, obstacle avoidance, motor control.
"""

from .pid_controller import PIDController
from .line_follower import LineFollower, LineFollowingStrategy, LineDetectionResult, ControlOutput
from .obstacle_avoider import ObstacleAvoider, AvoidanceStrategy, AvoidanceCommand, ObstacleData
from .motor_controller import MotorController, MotorControlMode, RobotKinematics, MotorCommand

__all__ = [
    'PIDController',
    'LineFollower',
    'LineFollowingStrategy',
    'LineDetectionResult',
    'ControlOutput',
    'ObstacleAvoider',
    'AvoidanceStrategy',
    'AvoidanceCommand',
    'ObstacleData',
    'MotorController',
    'MotorControlMode',
    'RobotKinematics',
    'MotorCommand',
]
