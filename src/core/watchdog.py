"""
Watchdog Module
System health monitoring and emergency stop mechanism.
"""

import threading
import time
import logging
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class RobotStatus(Enum):
    """System health status levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY_STOP = "emergency_stop"


class Watchdog:
    """
    Monitor robot system health and trigger emergency stop if needed.
    """
    
    def __init__(self, timeout_seconds: float = 1.0,
                 check_interval: float = 0.1) -> None:
        """
        Initialize watchdog.
        
        Args:
            timeout_seconds: Heartbeat timeout threshold
            check_interval: Monitoring check interval
        """
        self.timeout = timeout_seconds
        self.check_interval = check_interval
        self.last_heartbeat = time.time()
        self.status = RobotStatus.NORMAL
        self.lock = threading.RLock()
        self.running = False
        self.emergency_stop_callback: Optional[Callable] = None
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="Watchdog"
        )
        self.monitor_thread.start()
        self.running = True
    
    def heartbeat(self) -> None:
        """
        Signal system is alive. Call periodically from main loop.
        """
        with self.lock:
            self.last_heartbeat = time.time()
            self.status = RobotStatus.NORMAL
    
    def get_status(self) -> RobotStatus:
        """
        Get current system status.
        
        Returns:
            Current robot status
        """
        with self.lock:
            return self.status
    
    def set_emergency_callback(self, callback: Callable) -> None:
        """
        Register callback for emergency stop.
        
        Args:
            callback: Function to call on emergency
        """
        self.emergency_stop_callback = callback
    
    def _monitor_loop(self) -> None:
        """Monitor system health in background thread."""
        logger.info("Watchdog monitor started")
        
        try:
            while self.running:
                time.sleep(self.check_interval)
                
                with self.lock:
                    elapsed = time.time() - self.last_heartbeat
                    
                    # Update status based on elapsed time
                    if elapsed > self.timeout * 2:
                        if self.status != RobotStatus.EMERGENCY_STOP:
                            self.status = RobotStatus.EMERGENCY_STOP
                            logger.critical(
                                f"Watchdog timeout! No heartbeat for {elapsed:.2f}s"
                            )
                            self._trigger_emergency_stop()
                    
                    elif elapsed > self.timeout:
                        self.status = RobotStatus.CRITICAL
                        logger.warning(
                            f"Watchdog critical: No heartbeat for {elapsed:.2f}s"
                        )
                    
                    elif elapsed > self.timeout * 0.5:
                        self.status = RobotStatus.WARNING
        
        except Exception as e:
            logger.error(f"Watchdog monitor error: {e}")
        
        finally:
            logger.info("Watchdog monitor stopped")
    
    def _trigger_emergency_stop(self) -> None:
        """Trigger emergency stop procedure."""
        logger.critical("EMERGENCY STOP triggered by watchdog")
        
        if self.emergency_stop_callback:
            try:
                self.emergency_stop_callback()
            except Exception as e:
                logger.error(f"Error executing emergency callback: {e}")
        
        # Ensure motors are stopped
        try:
            from src.hardware.motors import Motors
            Motors().stop_all()
            logger.info("All motors stopped")
        except Exception as e:
            logger.error(f"Failed to stop motors: {e}")
    
    def stop(self) -> None:
        """Stop watchdog monitoring."""
        self.running = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        logger.info("Watchdog stopped")
