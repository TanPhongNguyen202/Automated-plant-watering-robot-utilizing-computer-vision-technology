"""
Logger Module
Centralized logging for the robot system with both file and console output.
"""

import logging
from datetime import datetime
from typing import Optional

# ============= Logging Configuration =============
DEFAULT_LOG_FILE = "robot.log"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class Logger:
    """
    Centralized logger for the robot system.
    Logs to both file and console with configurable verbosity.
    """
    
    def __init__(self, log_file: str = DEFAULT_LOG_FILE) -> None:
        """
        Initialize the logger with file and console handlers.
        
        Args:
            log_file: Path to log file (default: robot.log)
        """
        self.log_file = log_file
        
        # Configure root logger
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT
        )
        
        # Add console handler for real-time output
        self._console_handler = logging.StreamHandler()
        self._console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        self._console_handler.setFormatter(formatter)
        
        # Add console handler to root logger
        logging.getLogger().addHandler(self._console_handler)
    
    def log_info(self, message: str) -> None:
        """
        Log an info-level message.
        
        Args:
            message: The message to log
        """
        logging.info(message)
    
    def log_warning(self, message: str) -> None:
        """
        Log a warning-level message.
        
        Args:
            message: The message to log
        """
        logging.warning(message)
    
    def log_error(self, message: str) -> None:
        """
        Log an error-level message.
        
        Args:
            message: The message to log
        """
        logging.error(message)
    
    def log_critical(self, message: str) -> None:
        """
        Log a critical-level message.
        
        Args:
            message: The message to log
        """
        logging.critical(message)
    
    def log_debug(self, message: str) -> None:
        """
        Log a debug-level message.
        
        Args:
            message: The message to log
        """
        logging.debug(message)

    def log_debug(self, message):
        """
        Ghi log mức độ gỡ lỗi (debug).
        :param message: Nội dung gỡ lỗi cần ghi log.
        """
        logging.debug(message)

# Ví dụ sử dụng
if __name__ == "__main__":
    logger = Logger()
    logger.log_info("Robot initialized.")
    logger.log_warning("Battery level low.")
    logger.log_error("Obstacle detection failed.")
    logger.log_critical("System shutdown due to critical error.")
    logger.log_debug("Debugging motor control module.")
