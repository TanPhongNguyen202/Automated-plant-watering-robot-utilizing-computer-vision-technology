"""
Advanced Motor Control with Smooth Acceleration
Implements kinematic control with smooth acceleration ramping, current limiting,
and multi-motor coordination.
"""

import numpy as np
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum
import logging
import time

from src.utils.lifecycle_logger import LifecycleLogger


class MotorControlMode(Enum):
    """Motor control modes."""
    DIRECT = "direct"               # Direct PWM command
    VELOCITY = "velocity"           # Velocity control with ramping
    TORQUE = "torque"               # Torque-based control
    POSITION = "position"           # Position control (not for mobile robot)


@dataclass
class MotorCommand:
    """Single motor command."""
    speed: float         # -1.0 to 1.0
    acceleration: float  # Ramp rate (0-1 per second)
    max_current: float   # Maximum current in Amps


@dataclass
class RobotKinematics:
    """Differential drive kinematics."""
    wheel_radius: float           # Wheel radius in meters
    wheel_separation: float       # Distance between wheels in meters
    max_linear_velocity: float    # m/s
    max_angular_velocity: float   # rad/s


class MotorController:
    """
    Advanced motor controller with:
    - Smooth acceleration ramping
    - Current limiting
    - Multi-motor coordination
    - Kinematic model support
    - Real-time monitoring
    """
    
    def __init__(self,
                 num_motors: int = 4,
                 mode: MotorControlMode = MotorControlMode.VELOCITY,
                 kinematics: Optional[RobotKinematics] = None,
                 logger: Optional[LifecycleLogger] = None):
        """
        Initialize motor controller.
        
        Args:
            num_motors: Number of motors to control
            mode: Control mode to use
            kinematics: Optional kinematic model
            logger: Optional lifecycle logger
        """
        self.num_motors = num_motors
        self.mode = mode
        self.kinematics = kinematics or RobotKinematics(
            wheel_radius=0.05,  # 5cm wheels
            wheel_separation=0.15,  # 15cm wheelbase
            max_linear_velocity=0.5,  # 0.5 m/s
            max_angular_velocity=2.0   # 2 rad/s
        )
        self.logger = logger or LifecycleLogger()
        
        # ========== Motor State ==========
        self.current_speeds = np.zeros(num_motors)  # Current speed 0-1
        self.target_speeds = np.zeros(num_motors)   # Target speed -1 to 1
        self.accelerations = np.ones(num_motors) * 0.5  # Default ramp rate
        self.motor_currents = np.zeros(num_motors)  # Current consumption (A)
        self.max_currents = np.ones(num_motors) * 2.0  # Current limits (A)
        
        # ========== Control Limits ==========
        self.max_acceleration = 2.0  # Max ramp rate (0-1 per second)
        self.min_speed_threshold = 0.05  # Below this, consider stopped
        
        # ========== Timing ==========
        self.last_update = time.time()
        self.dt = 0.01  # Control timestep
        
        # ========== Performance Tracking ==========
        self.total_motor_hours = np.zeros(num_motors)
        self.current_limit_events = 0
        self.command_count = 0
        self.speed_profile_history: List[np.ndarray] = []
        
        logging.info(f"MotorController initialized: {num_motors} motors, "
                    f"mode={mode.value}")
    
    def set_target_speed(self, motor_indices: List[int], 
                        speeds: List[float],
                        accelerations: Optional[List[float]] = None) -> None:
        """
        Set target speeds for motors with smooth ramping.
        
        Args:
            motor_indices: Indices of motors to control
            speeds: Target speeds (-1 to 1)
            accelerations: Optional ramp rates per motor
        """
        for i, idx in enumerate(motor_indices):
            if 0 <= idx < self.num_motors:
                self.target_speeds[idx] = np.clip(speeds[i], -1.0, 1.0)
                
                if accelerations:
                    self.accelerations[idx] = np.clip(
                        accelerations[i], 0.0, self.max_acceleration
                    )
        
        self.command_count += 1
    
    def set_velocity_command(self, linear_velocity: float,
                            angular_velocity: float) -> None:
        """
        Set robot velocity using kinematic model.
        
        Uses differential drive kinematics to compute motor speeds.
        
        Args:
            linear_velocity: Forward velocity (-1 to 1)
            angular_velocity: Rotational velocity (-1 to 1)
        """
        # Normalize inputs
        linear_velocity = np.clip(linear_velocity, -1.0, 1.0)
        angular_velocity = np.clip(angular_velocity, -1.0, 1.0)
        
        # Differential drive kinematics
        # For a 4-wheel robot: left_front, left_rear, right_front, right_rear
        # Left motors: v_left = v_linear - v_angular * L/2
        # Right motors: v_right = v_linear + v_angular * L/2
        
        v_left = linear_velocity - angular_velocity * 0.5
        v_right = linear_velocity + angular_velocity * 0.5
        
        # Normalize if exceeding max
        max_v = max(abs(v_left), abs(v_right), 1.0)
        v_left /= max_v
        v_right /= max_v
        
        # Apply to motors (assuming [left_front, right_front, left_rear, right_rear])
        self.set_target_speed(
            motor_indices=[0, 2],  # Left motors
            speeds=[v_left, v_left],
            accelerations=[0.5, 0.5]
        )
        
        self.set_target_speed(
            motor_indices=[1, 3],  # Right motors
            speeds=[v_right, v_right],
            accelerations=[0.5, 0.5]
        )
    
    def update(self) -> np.ndarray:
        """
        Update motor controller and compute new PWM outputs.
        
        Implements smooth acceleration ramping to prevent motor jerk
        and mechanical shock.
        
        Returns:
            Array of motor PWM values (-1.0 to 1.0)
        """
        current_time = time.time()
        dt = current_time - self.last_update
        dt = np.clip(dt, 0.001, 0.1)  # Clamp dt to reasonable range
        self.last_update = current_time
        
        # Apply smooth acceleration ramping
        for i in range(self.num_motors):
            speed_diff = self.target_speeds[i] - self.current_speeds[i]
            max_change = self.accelerations[i] * dt
            
            if abs(speed_diff) > max_change:
                # Ramp toward target
                direction = np.sign(speed_diff)
                self.current_speeds[i] += direction * max_change
            else:
                # Reached target
                self.current_speeds[i] = self.target_speeds[i]
        
        # Apply deadband
        self.current_speeds[np.abs(self.current_speeds) < self.min_speed_threshold] = 0.0
        
        # Simulate current draw (proportional to speed and load)
        # Real implementation would read from current sensors
        self.motor_currents = np.abs(self.current_speeds) * 2.0
        
        # Check current limits
        overcurrent_motors = np.where(
            self.motor_currents > self.max_currents
        )[0]
        
        if len(overcurrent_motors) > 0:
            self.current_limit_events += 1
            logging.warning(f"Motor overcurrent: {overcurrent_motors}")
            self.logger.log_hardware_fault(
                "motor_controller",
                f"Overcurrent on motors {overcurrent_motors}",
                "WARNING"
            )
            # Limit speeds of overcurrent motors
            for idx in overcurrent_motors:
                self.current_speeds[idx] *= 0.8
        
        # Store speed profile for analysis
        if self.command_count % 10 == 0:  # Every 10 commands
            self.speed_profile_history.append(self.current_speeds.copy())
            if len(self.speed_profile_history) > 1000:  # Limit history size
                self.speed_profile_history.pop(0)
        
        return self.current_speeds.copy()
    
    def emergency_stop(self) -> None:
        """Emergency stop all motors."""
        self.target_speeds.fill(0.0)
        self.current_speeds.fill(0.0)
        logging.warning("Emergency stop activated - all motors stopped")
        self.logger.log_hardware_fault("motor_controller",
                                       "Emergency stop", "CRITICAL")
    
    def stop_motor(self, motor_index: int, 
                  deceleration: float = 2.0) -> None:
        """
        Stop single motor with controlled deceleration.
        
        Args:
            motor_index: Motor to stop
            deceleration: Deceleration rate (0-2)
        """
        if 0 <= motor_index < self.num_motors:
            self.target_speeds[motor_index] = 0.0
            self.accelerations[motor_index] = deceleration
    
    def stop_all_motors(self, deceleration: float = 1.0) -> None:
        """
        Stop all motors with controlled deceleration.
        
        Args:
            deceleration: Deceleration rate (0-2)
        """
        self.target_speeds.fill(0.0)
        self.accelerations.fill(deceleration)
    
    def set_mode(self, mode: MotorControlMode) -> None:
        """
        Change control mode.
        
        Args:
            mode: New control mode
        """
        self.mode = mode
        logging.info(f"Motor control mode changed to: {mode.value}")
    
    def get_current_speeds(self) -> np.ndarray:
        """Get current motor speeds."""
        return self.current_speeds.copy()
    
    def get_motor_status(self, motor_index: int) -> Dict[str, float]:
        """
        Get detailed status of single motor.
        
        Args:
            motor_index: Motor index
        
        Returns:
            Dictionary with motor status
        """
        if not (0 <= motor_index < self.num_motors):
            raise ValueError(f"Invalid motor index: {motor_index}")
        
        return {
            'current_speed': float(self.current_speeds[motor_index]),
            'target_speed': float(self.target_speeds[motor_index]),
            'acceleration': float(self.accelerations[motor_index]),
            'current_amps': float(self.motor_currents[motor_index]),
            'max_current': float(self.max_currents[motor_index]),
            'motor_hours': float(self.total_motor_hours[motor_index]),
        }
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Get overall performance metrics.
        
        Returns:
            Dictionary with metrics
        """
        avg_speed = np.mean(np.abs(self.current_speeds))
        
        return {
            'average_speed': float(avg_speed),
            'max_speed': float(np.max(np.abs(self.current_speeds))),
            'total_motor_hours': float(np.sum(self.total_motor_hours)),
            'average_current': float(np.mean(self.motor_currents)),
            'max_current': float(np.max(self.motor_currents)),
            'current_limit_events': float(self.current_limit_events),
            'total_commands': float(self.command_count),
        }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.total_motor_hours.fill(0.0)
        self.current_limit_events = 0
        self.command_count = 0
        self.speed_profile_history = []
        logging.info("MotorController metrics reset")
