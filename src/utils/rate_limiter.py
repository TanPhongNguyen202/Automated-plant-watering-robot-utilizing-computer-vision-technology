"""
Rate Limiter Module
Limit loop execution frequency to specified rate.
"""

import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Limit execution frequency of code blocks.
    Useful for controlling loop rates in robotics.
    """
    
    def __init__(self, frequency_hz: float) -> None:
        """
        Initialize rate limiter.
        
        Args:
            frequency_hz: Target frequency in Hz
        
        Raises:
            ValueError: If frequency is not positive
        """
        if frequency_hz <= 0:
            raise ValueError("Frequency must be positive")
        
        self.frequency = frequency_hz
        self.period = 1.0 / frequency_hz
        self.last_time = time.time()
        self.iteration_count = 0
        self.start_time = self.last_time
    
    def sleep(self) -> float:
        """
        Sleep to maintain desired frequency.
        
        Returns:
            Actual elapsed time since last call
        """
        current_time = time.time()
        elapsed = current_time - self.last_time
        
        # Calculate sleep time
        sleep_time = self.period - elapsed
        
        if sleep_time > 0:
            time.sleep(sleep_time)
            actual_elapsed = time.time() - self.last_time
        else:
            actual_elapsed = elapsed
        
        self.last_time = time.time()
        self.iteration_count += 1
        
        return actual_elapsed
    
    def get_actual_frequency(self) -> float:
        """
        Get actual measured frequency.
        
        Returns:
            Actual frequency in Hz
        """
        elapsed_time = time.time() - self.start_time
        if elapsed_time <= 0:
            return 0.0
        return self.iteration_count / elapsed_time
    
    def reset(self) -> None:
        """Reset rate limiter."""
        self.last_time = time.time()
        self.iteration_count = 0
        self.start_time = self.last_time
