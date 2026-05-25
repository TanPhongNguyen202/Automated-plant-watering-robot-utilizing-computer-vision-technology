"""
Safe Stop Module
Emergency and graceful shutdown mechanisms.
"""

import logging
import threading
import time
from typing import Callable, List

logger = logging.getLogger(__name__)


class SafeStop:
    """
    Manage graceful shutdown and emergency stopping procedures.
    """
    
    def __init__(self) -> None:
        """Initialize safe stop handler."""
        self.shutdown_handlers: List[Callable] = []
        self.emergency_handlers: List[Callable] = []
        self.is_stopping = False
        self.stop_lock = threading.RLock()
    
    def register_shutdown_handler(self, handler: Callable) -> None:
        """
        Register handler for graceful shutdown.
        
        Args:
            handler: Function to call during shutdown
        """
        if handler not in self.shutdown_handlers:
            self.shutdown_handlers.append(handler)
            logger.debug(f"Registered shutdown handler: {handler.__name__}")
    
    def register_emergency_handler(self, handler: Callable) -> None:
        """
        Register handler for emergency stop.
        
        Args:
            handler: Function to call during emergency
        """
        if handler not in self.emergency_handlers:
            self.emergency_handlers.append(handler)
            logger.debug(f"Registered emergency handler: {handler.__name__}")
    
    def graceful_shutdown(self, timeout_seconds: float = 5.0) -> None:
        """
        Perform graceful shutdown.
        
        Args:
            timeout_seconds: Maximum time to wait for shutdown
        """
        with self.stop_lock:
            if self.is_stopping:
                logger.warning("Shutdown already in progress")
                return
            
            self.is_stopping = True
        
        logger.info("Initiating graceful shutdown")
        
        try:
            # Execute all shutdown handlers in sequence
            for i, handler in enumerate(self.shutdown_handlers):
                try:
                    logger.info(f"Executing shutdown handler {i+1}/{len(self.shutdown_handlers)}")
                    handler()
                except Exception as e:
                    logger.error(f"Error in shutdown handler: {e}")
            
            logger.info("Graceful shutdown completed")
        
        except Exception as e:
            logger.error(f"Unexpected error during shutdown: {e}")
    
    def emergency_stop(self) -> None:
        """
        Trigger emergency stop immediately.
        """
        with self.stop_lock:
            if self.is_stopping:
                logger.warning("Emergency stop already triggered")
                return
            
            self.is_stopping = True
        
        logger.critical("EMERGENCY STOP TRIGGERED")
        
        # Execute emergency handlers immediately
        for handler in self.emergency_handlers:
            try:
                logger.info(f"Executing emergency handler: {handler.__name__}")
                handler()
            except Exception as e:
                logger.error(f"Error in emergency handler: {e}")
        
        # Force motor stop
        try:
            from src.hardware.motors import Motors
            Motors().stop_all()
            logger.info("Emergency stop: All motors stopped")
        except Exception as e:
            logger.error(f"Failed to stop motors: {e}")
    
    def is_shutting_down(self) -> bool:
        """
        Check if shutdown is in progress.
        
        Returns:
            True if stopping or shutdown in progress
        """
        with self.stop_lock:
            return self.is_stopping
