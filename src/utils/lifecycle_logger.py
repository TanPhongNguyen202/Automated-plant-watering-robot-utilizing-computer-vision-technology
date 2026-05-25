"""
Lifecycle Logger Module
Comprehensive logging for system analysis and debugging.
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Create log directory
LOG_DIR = Path("/var/log/robot") if Path("/var").exists() else Path("logs")
LOG_DIR.mkdir(exist_ok=True, parents=True)


class LifecycleLogger:
    """
    Structured logging for robot system events with multiple levels.
    """
    
    def __init__(self, session_id: Optional[str] = None) -> None:
        """
        Initialize lifecycle logger.
        
        Args:
            session_id: Custom session identifier (auto-generated if None)
        """
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = datetime.now()
        
        # Create loggers for different levels
        self.event_log = self._create_logger("events", "events")
        self.error_log = self._create_logger("errors", "errors")
        self.trace_log = self._create_logger("trace", "trace")
        
        self.event_log.info(f"Session started: {self.session_id}")
    
    def _create_logger(self, name: str, log_type: str) -> logging.Logger:
        """
        Create a logger with file handler.
        
        Args:
            name: Logger name
            log_type: Type of log (events, errors, trace)
        
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(f"robot.{log_type}")
        logger.setLevel(logging.DEBUG if log_type == "trace" else logging.INFO)
        
        # Create file handler
        log_file = LOG_DIR / f"{self.session_id}_{log_type}.log"
        handler = logging.FileHandler(log_file)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def log_state_transition(self, from_state: str, to_state: str, 
                            reason: str = "") -> None:
        """
        Log state machine transition.
        
        Args:
            from_state: Source state
            to_state: Target state
            reason: Reason for transition
        """
        msg = f"STATE_CHANGE: {from_state} -> {to_state}"
        if reason:
            msg += f" | Reason: {reason}"
        self.event_log.info(msg)
    
    def log_hardware_fault(self, component: str, error: str, 
                          severity: str = "ERROR") -> None:
        """
        Log hardware fault.
        
        Args:
            component: Hardware component name
            error: Error description
            severity: Severity level
        """
        msg = f"HARDWARE_FAULT: {component} | {error} | Severity: {severity}"
        self.error_log.error(msg)
        
        # Also log to events for overview
        self.event_log.warning(msg)
    
    def log_periodic_snapshot(self, data: Dict[str, Any]) -> None:
        """
        Log periodic system snapshot for debugging.
        
        Args:
            data: System state snapshot dictionary
        """
        try:
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id,
                **data
            }
            self.trace_log.debug(json.dumps(snapshot))
        except Exception as e:
            self.error_log.error(f"Error logging snapshot: {e}")
    
    def log_mission_event(self, event: str, details: str = "") -> None:
        """
        Log mission-related events.
        
        Args:
            event: Event name
            details: Additional details
        """
        msg = f"MISSION_EVENT: {event}"
        if details:
            msg += f" | {details}"
        self.event_log.info(msg)
    
    def log_sensor_reading(self, sensor_name: str, value: Any, 
                          unit: str = "") -> None:
        """
        Log sensor reading.
        
        Args:
            sensor_name: Name of sensor
            value: Sensor value
            unit: Unit of measurement
        """
        msg = f"SENSOR: {sensor_name} = {value}"
        if unit:
            msg += f" {unit}"
        self.trace_log.debug(msg)
    
    def log_performance_metric(self, metric_name: str, value: float,
                             threshold: Optional[float] = None) -> None:
        """
        Log performance metric.
        
        Args:
            metric_name: Name of metric
            value: Metric value
            threshold: Alert threshold (optional)
        """
        msg = f"METRIC: {metric_name} = {value:.2f}"
        
        if threshold and value > threshold:
            self.event_log.warning(msg + f" (exceeds threshold {threshold})")
        else:
            self.event_log.info(msg)
    
    def get_log_files(self) -> Dict[str, Path]:
        """
        Get paths to all log files for this session.
        
        Returns:
            Dictionary mapping log type to file path
        """
        return {
            'events': LOG_DIR / f"{self.session_id}_events.log",
            'errors': LOG_DIR / f"{self.session_id}_errors.log",
            'trace': LOG_DIR / f"{self.session_id}_trace.log"
        }
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get session summary.
        
        Returns:
            Dictionary with session information
        """
        duration = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'session_id': self.session_id,
            'start_time': self.start_time.isoformat(),
            'duration_seconds': duration,
            'log_files': {k: str(v) for k, v in self.get_log_files().items()}
        }
