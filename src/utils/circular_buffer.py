"""
Circular Buffer Module
Fixed-size buffer for efficient time-series data storage.
"""

from collections import deque
from typing import Any, List, Optional
import numpy as np


class CircularBuffer:
    """
    Fixed-size circular buffer for efficient storage of sensor data.
    """
    
    def __init__(self, max_size: int) -> None:
        """
        Initialize circular buffer.
        
        Args:
            max_size: Maximum number of elements to store
        
        Raises:
            ValueError: If max_size is not positive
        """
        if max_size <= 0:
            raise ValueError("Buffer size must be positive")
        
        self.max_size = max_size
        self.buffer: deque = deque(maxlen=max_size)
    
    def append(self, value: Any) -> None:
        """
        Add value to buffer. Oldest value is removed if full.
        
        Args:
            value: Value to add
        """
        self.buffer.append(value)
    
    def get_all(self) -> List[Any]:
        """
        Get all values in buffer.
        
        Returns:
            List of all buffered values
        """
        return list(self.buffer)
    
    def get_average(self) -> Optional[float]:
        """
        Calculate average of buffer values (numeric only).
        
        Returns:
            Average value or None if buffer empty
        """
        if not self.buffer:
            return None
        
        try:
            return sum(self.buffer) / len(self.buffer)
        except (TypeError, ValueError):
            return None
    
    def get_last(self, n: int) -> List[Any]:
        """
        Get last n values.
        
        Args:
            n: Number of last values
        
        Returns:
            List of last n values
        """
        return list(self.buffer)[-n:] if n > 0 else []
    
    def is_full(self) -> bool:
        """
        Check if buffer is full.
        
        Returns:
            True if buffer is at max capacity
        """
        return len(self.buffer) == self.max_size
    
    def is_empty(self) -> bool:
        """
        Check if buffer is empty.
        
        Returns:
            True if buffer is empty
        """
        return len(self.buffer) == 0
    
    def get_size(self) -> int:
        """
        Get current buffer size.
        
        Returns:
            Number of elements in buffer
        """
        return len(self.buffer)
    
    def clear(self) -> None:
        """Clear all values from buffer."""
        self.buffer.clear()
    
    def get_numpy_array(self) -> Optional[np.ndarray]:
        """
        Get buffer as numpy array (numeric values only).
        
        Returns:
            Numpy array or None if empty
        """
        if not self.buffer:
            return None
        
        try:
            return np.array(list(self.buffer))
        except (TypeError, ValueError):
            return None
