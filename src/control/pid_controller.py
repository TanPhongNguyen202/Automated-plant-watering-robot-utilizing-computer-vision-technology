"""
PID Controller Module
Proportional-Integral-Derivative control for line tracking.
"""

import time
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class PIDController:
    """
    PID controller with anti-windup and output limiting.
    """
    
    def __init__(self, kp: float, ki: float, kd: float,
                 output_limits: Tuple[float, float] = (-1.0, 1.0),
                 integral_limit: float = 1.0) -> None:
        """
        Initialize PID controller.
        
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            output_limits: (min, max) output limits
            integral_limit: Maximum integral term magnitude (anti-windup)
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.limits = output_limits
        self.integral_limit = integral_limit
        
        # State variables
        self.integral = 0.0
        self.previous_error = 0.0
        self.last_time = time.time()
        self.last_output = 0.0
        
        # Statistics
        self.update_count = 0
        self.total_error = 0.0
    
    def update(self, error: float) -> float:
        """
        Calculate PID output for given error.
        
        Args:
            error: Current error value
        
        Returns:
            PID control output
        """
        current_time = time.time()
        dt = current_time - self.last_time
        
        # Prevent division by zero
        if dt <= 0:
            dt = 0.001
        
        # Proportional term
        p_term = self.kp * error
        
        # Integral term with anti-windup
        self.integral += error * dt
        self.integral = max(-self.integral_limit, 
                           min(self.integral_limit, self.integral))
        i_term = self.ki * self.integral
        
        # Derivative term
        derivative = (error - self.previous_error) / dt
        d_term = self.kd * derivative
        
        # Calculate output
        output = p_term + i_term + d_term
        
        # Apply output limits
        output = max(self.limits[0], min(self.limits[1], output))
        
        # Update state
        self.previous_error = error
        self.last_time = current_time
        self.last_output = output
        
        # Update statistics
        self.update_count += 1
        self.total_error += abs(error)
        
        return output
    
    def reset(self) -> None:
        """Reset controller state."""
        self.integral = 0.0
        self.previous_error = 0.0
        self.last_time = time.time()
        self.last_output = 0.0
        logger.debug("PID controller reset")
    
    def set_gains(self, kp: float, ki: float, kd: float) -> None:
        """
        Update PID gains.
        
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        logger.debug(f"PID gains updated: kp={kp}, ki={ki}, kd={kd}")
    
    def get_statistics(self) -> dict:
        """
        Get controller statistics.
        
        Returns:
            Dictionary with statistics
        """
        avg_error = (self.total_error / self.update_count 
                    if self.update_count > 0 else 0)
        
        return {
            'update_count': self.update_count,
            'average_error': avg_error,
            'integral_term': self.integral,
            'last_output': self.last_output
        }
