"""
State Machine Module
Manages robot operational states and transitions with validation.
"""

from enum import Enum, auto
from typing import Callable, Dict, Optional
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RobotState(Enum):
    """Robot operational states."""
    INIT = auto()
    IDLE = auto()
    MANUAL = auto()
    AUTO_MISSION = auto()
    RETURN_TO_CHARGER = auto()
    CHARGING = auto()
    OBSTACLE_AVOID = auto()
    WATERING = auto()
    SEARCHING = auto()
    ERROR = auto()
    EMERGENCY_STOP = auto()


class StateMachine:
    """
    Finite state machine for robot operation.
    Ensures valid state transitions and manages callbacks.
    """
    
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        """
        Initialize state machine.
        
        Args:
            timeout_seconds: Maximum time in a state before transition required
        """
        self.current_state = RobotState.INIT
        self.previous_state: Optional[RobotState] = None
        self.state_timeout = timeout_seconds
        self.state_start_time = time.time()
        self.transition_callbacks: Dict[RobotState, Callable] = {}
        self.state_entry_time = time.time()
        
        # Define valid state transitions
        self._init_transitions()
    
    def _init_transitions(self) -> None:
        """Initialize valid state transitions."""
        self.allowed_transitions = {
            RobotState.INIT: [RobotState.IDLE, RobotState.ERROR],
            RobotState.IDLE: [
                RobotState.MANUAL,
                RobotState.AUTO_MISSION,
                RobotState.RETURN_TO_CHARGER,
                RobotState.ERROR
            ],
            RobotState.MANUAL: [
                RobotState.IDLE,
                RobotState.ERROR,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.AUTO_MISSION: [
                RobotState.WATERING,
                RobotState.SEARCHING,
                RobotState.OBSTACLE_AVOID,
                RobotState.IDLE,
                RobotState.RETURN_TO_CHARGER,
                RobotState.ERROR,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.WATERING: [
                RobotState.AUTO_MISSION,
                RobotState.RETURN_TO_CHARGER,
                RobotState.ERROR,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.SEARCHING: [
                RobotState.AUTO_MISSION,
                RobotState.RETURN_TO_CHARGER,
                RobotState.ERROR,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.OBSTACLE_AVOID: [
                RobotState.AUTO_MISSION,
                RobotState.RETURN_TO_CHARGER,
                RobotState.ERROR,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.RETURN_TO_CHARGER: [
                RobotState.CHARGING,
                RobotState.IDLE,
                RobotState.ERROR,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.CHARGING: [
                RobotState.IDLE,
                RobotState.ERROR,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.ERROR: [
                RobotState.IDLE,
                RobotState.EMERGENCY_STOP
            ],
            RobotState.EMERGENCY_STOP: [
                RobotState.IDLE,
                RobotState.ERROR
            ]
        }
    
    def transition_to(self, new_state: RobotState, reason: str = "") -> bool:
        """
        Transition to a new state with validation.
        
        Args:
            new_state: Target state
            reason: Reason for transition (for logging)
        
        Returns:
            True if transition successful, False if invalid
        """
        # Validate transition
        allowed = self.allowed_transitions.get(self.current_state, [])
        if new_state not in allowed:
            logger.error(
                f"Invalid state transition: {self.current_state.name} -> "
                f"{new_state.name}"
            )
            return False
        
        # Record transition
        self.previous_state = self.current_state
        self.current_state = new_state
        self.state_start_time = time.time()
        self.state_entry_time = datetime.now()
        
        # Log transition
        log_msg = f"STATE_CHANGE: {self.previous_state.name} -> {new_state.name}"
        if reason:
            log_msg += f" | Reason: {reason}"
        logger.info(log_msg)
        
        # Execute callback if registered
        if new_state in self.transition_callbacks:
            try:
                self.transition_callbacks[new_state]()
            except Exception as e:
                logger.error(f"Error executing callback for {new_state.name}: {e}")
        
        return True
    
    def add_callback(self, state: RobotState, callback: Callable) -> None:
        """
        Register callback for state entry.
        
        Args:
            state: State to register callback for
            callback: Function to call on state entry
        """
        self.transition_callbacks[state] = callback
        logger.debug(f"Registered callback for state {state.name}")
    
    def get_state_duration(self) -> float:
        """
        Get time spent in current state.
        
        Returns:
            Duration in seconds
        """
        return time.time() - self.state_start_time
    
    def is_timeout(self) -> bool:
        """
        Check if state timeout exceeded.
        
        Returns:
            True if timeout exceeded
        """
        return self.get_state_duration() > self.state_timeout
    
    def reset(self) -> None:
        """Reset state machine to INIT."""
        self.transition_to(RobotState.INIT, reason="Manual reset")
