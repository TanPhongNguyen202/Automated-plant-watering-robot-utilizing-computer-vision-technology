"""
Battery Monitoring Module
Monitors battery voltage, current, and power using INA219 sensor.
Provides battery status and remaining time estimates.
"""

from ina219 import INA219  # type: ignore
from collections import deque
from typing import Tuple, Optional
from src.utils.logger import Logger

# ============= Battery Configuration =============
INA219_ADDRESS = 0x40
INA219_BUS_NUMBER = 1
SHUNT_OHMS = 0.1
FULL_VOLTAGE = 16.8  # Fully charged voltage (V)
MIN_VOLTAGE = 14.8   # Minimum safe voltage (V)
BATTERY_CAPACITY_AH = 13.6
CURRENT_HISTORY_SIZE = 20

# ============= Logging =============
logger = Logger()


class BatteryMonitor:
    """
    Monitor battery status using INA219 current/voltage sensor.
    """
    
    def __init__(self) -> None:
        """Initialize INA219 sensor and configure for battery monitoring."""
        self.ina: Optional[INA219] = None
        self.current_history: deque = deque(maxlen=CURRENT_HISTORY_SIZE)
        
        try:
            self.ina = INA219(SHUNT_OHMS, address=INA219_ADDRESS, 
                            busnum=INA219_BUS_NUMBER)
            self.ina.configure()
            logger.log_info("INA219 battery monitor initialized successfully")
        
        except Exception as e:
            logger.log_error(f"Failed to initialize INA219: {e}")
            self.ina = None
    
    def read_battery_status(self) -> Tuple[Optional[float], Optional[float], 
                                          Optional[float], float, float]:
        """
        Read battery status including voltage, current, power, percentage, 
        and estimated remaining time.
        
        Returns:
            Tuple of (voltage, current, power, percentage, remaining_hours)
            Returns safe defaults if sensor is unavailable
        """
        if self.ina is None:
            logger.log_warning("INA219 sensor not available, returning default values")
            return None, None, None, 0.0, float('inf')
        
        try:
            voltage = self.ina.voltage()  # Bus voltage (V)
            current = self.ina.current()  # Current (mA)
            power = self.ina.power()      # Power (mW)
            
            # Store current for averaging
            self.current_history.append(current)
            
            # Calculate average current
            avg_current = (sum(self.current_history) / 
                          len(self.current_history))
            
            # Calculate battery percentage
            voltage_range = FULL_VOLTAGE - MIN_VOLTAGE
            battery_percentage = max(0, min(100, 
                (voltage - MIN_VOLTAGE) / voltage_range * 100))
            
            # Calculate remaining capacity
            remaining_capacity_ah = BATTERY_CAPACITY_AH * (battery_percentage / 100)
            
            # Calculate remaining time (hours)
            if avg_current > 0:
                remaining_time_hours = remaining_capacity_ah / (avg_current / 1000)
            else:
                remaining_time_hours = float('inf')
            
            return voltage, current, power, battery_percentage, remaining_time_hours
        
        except Exception as e:
            logger.log_error(f"Error reading battery status: {e}")
            return None, None, None, 0.0, float('inf')
    
    def display_battery_status(self) -> None:
        """
        Display formatted battery status information.
        """
        voltage, current, power, percentage, remaining_hours = self.read_battery_status()
        
        if voltage is not None:
            status_msg = (
                f"Battery Status | "
                f"Voltage: {voltage:.2f}V | "
                f"Current: {current:.2f}mA | "
                f"Power: {power:.2f}mW | "
                f"Level: {percentage:.1f}% | "
                f"Remaining: {remaining_hours:.1f}h"
            )
            logger.log_info(status_msg)
        else:
            logger.log_warning("Failed to read battery status - sensor unavailable")
