"""
Sophisticated Obstacle Avoidance Controller
Implements multiple avoidance strategies with sensor fusion and path planning.
Supports wall following, random walk, and dynamic obstacle detection.
"""

import numpy as np
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import time
import math

from src.utils.circular_buffer import CircularBuffer
from src.utils.lifecycle_logger import LifecycleLogger


class AvoidanceStrategy(Enum):
    """Obstacle avoidance strategies."""
    WALL_FOLLOWING = "wall_following"    # Follow wall using distance sensor
    RANDOM_WALK = "random_walk"          # Random direction changes
    POTENTIAL_FIELD = "potential_field"  # Virtual potential field method
    BUG_ALGORITHM = "bug_algorithm"      # BUG algorithm (wall + target)
    HYBRID = "hybrid"                    # Combine multiple strategies


@dataclass
class ObstacleData:
    """Sensor data for obstacle detection."""
    front_distance: float    # Forward direction distance (meters)
    left_distance: float     # Left direction distance (meters)
    right_distance: float    # Right direction distance (meters)
    rear_distance: Optional[float]  # Rear distance (optional)
    timestamp: float


@dataclass
class AvoidanceCommand:
    """Obstacle avoidance command output."""
    linear_velocity: float    # -1.0 to 1.0 (forward/backward)
    angular_velocity: float   # -1.0 to 1.0 (rotation)
    strategy_used: AvoidanceStrategy
    obstacle_detected: bool
    confidence: float  # 0-1, higher = more certain about command


class ObstacleAvoider:
    """
    Multi-strategy obstacle avoidance controller with sensor fusion.
    
    Features:
    - Wall following algorithm
    - Random walk with memory
    - Potential field method
    - BUG algorithm for target-based navigation
    - Hybrid approach combining multiple methods
    - Sensor data smoothing and filtering
    """
    
    def __init__(self,
                 strategy: AvoidanceStrategy = AvoidanceStrategy.WALL_FOLLOWING,
                 critical_distance: float = 0.3,  # meters
                 safe_distance: float = 0.5,      # meters
                 logger: Optional[LifecycleLogger] = None):
        """
        Initialize obstacle avoider.
        
        Args:
            strategy: Initial avoidance strategy
            critical_distance: Minimum safe distance (stop if closer)
            safe_distance: Preferred minimum distance
            logger: Optional lifecycle logger
        """
        self.strategy = strategy
        self.critical_distance = critical_distance
        self.safe_distance = safe_distance
        self.logger = logger or LifecycleLogger()
        
        # ========== Sensor Filtering ==========
        self.sensor_buffer_size = 5
        self.front_distance_buffer = CircularBuffer(self.sensor_buffer_size)
        self.left_distance_buffer = CircularBuffer(self.sensor_buffer_size)
        self.right_distance_buffer = CircularBuffer(self.sensor_buffer_size)
        self.rear_distance_buffer = CircularBuffer(self.sensor_buffer_size)
        
        # ========== Wall Following State ==========
        self.wall_follow_side = "right"  # "left" or "right"
        self.wall_distance_target = self.safe_distance * 1.2
        self.last_wall_distance = None
        
        # ========== Random Walk State ==========
        self.random_walk_direction = 0  # Current direction (degrees)
        self.random_walk_duration = 2.0  # Duration per direction (seconds)
        self.random_walk_last_change = time.time()
        
        # ========== BUG Algorithm State ==========
        self.target_position = (0, 0)  # Goal position (x, y)
        self.robot_position = (0, 0)  # Current position
        self.bug_state = "going_to_goal"  # "going_to_goal" or "following_wall"
        
        # ========== Path Memory ==========
        self.path_history: List[Tuple[float, float]] = []
        self.obstacle_locations: Dict[Tuple[int, int], float] = {}  # Grid-based memory
        self.grid_resolution = 0.5  # meters per grid cell
        
        # ========== Performance Tracking ==========
        self.collision_count = 0
        self.avoidance_maneuvers = 0
        self.strategy_changes = 0
        
        logging.info(f"ObstacleAvoider initialized: strategy={strategy.value}, "
                    f"critical_distance={critical_distance}m, "
                    f"safe_distance={safe_distance}m")
    
    def update_sensors(self, obstacle_data: ObstacleData) -> None:
        """
        Update sensor readings with smoothing/filtering.
        
        Args:
            obstacle_data: Current sensor readings
        """
        self.front_distance_buffer.append(obstacle_data.front_distance)
        self.left_distance_buffer.append(obstacle_data.left_distance)
        self.right_distance_buffer.append(obstacle_data.right_distance)
        
        if obstacle_data.rear_distance is not None:
            self.rear_distance_buffer.append(obstacle_data.rear_distance)
    
    def get_smoothed_distances(self) -> Dict[str, float]:
        """
        Get smoothed (averaged) sensor distances.
        
        Returns:
            Dictionary with smoothed distances
        """
        return {
            'front': self.front_distance_buffer.get_average(),
            'left': self.left_distance_buffer.get_average(),
            'right': self.right_distance_buffer.get_average(),
            'rear': self.rear_distance_buffer.get_average() 
                   if not self.rear_distance_buffer.is_empty() else None,
        }
    
    def calculate_avoidance(self, obstacle_data: ObstacleData) -> AvoidanceCommand:
        """
        Calculate avoidance maneuver based on current strategy.
        
        Args:
            obstacle_data: Current sensor readings
        
        Returns:
            AvoidanceCommand with motor control outputs
        """
        self.update_sensors(obstacle_data)
        smoothed = self.get_smoothed_distances()
        
        # Check for critical distance
        if smoothed['front'] < self.critical_distance:
            self.collision_count += 1
            return self._emergency_stop()
        
        # Execute strategy
        if self.strategy == AvoidanceStrategy.WALL_FOLLOWING:
            return self._wall_following(smoothed)
        elif self.strategy == AvoidanceStrategy.RANDOM_WALK:
            return self._random_walk(smoothed)
        elif self.strategy == AvoidanceStrategy.POTENTIAL_FIELD:
            return self._potential_field(smoothed)
        elif self.strategy == AvoidanceStrategy.BUG_ALGORITHM:
            return self._bug_algorithm(smoothed)
        else:  # HYBRID
            return self._hybrid_strategy(smoothed)
    
    def _emergency_stop(self) -> AvoidanceCommand:
        """Emergency stop when obstacle is too close."""
        logging.warning("OBSTACLE: Emergency stop activated")
        self.logger.log_hardware_fault("obstacle_avoider", 
                                       "Critical distance reached", 
                                       "CRITICAL")
        
        return AvoidanceCommand(
            linear_velocity=-0.3,  # Slight backward
            angular_velocity=0.5,   # Turn to escape
            strategy_used=self.strategy,
            obstacle_detected=True,
            confidence=1.0
        )
    
    def _wall_following(self, distances: Dict[str, float]) -> AvoidanceCommand:
        """
        Wall following strategy: maintain constant distance from wall.
        
        Args:
            distances: Smoothed sensor distances
        
        Returns:
            Control command
        """
        front = distances['front']
        left = distances['left']
        right = distances['right']
        
        # Obstacle detection
        obstacle_detected = front < self.safe_distance
        
        # Choose wall to follow if not already following
        if self.last_wall_distance is None:
            if left < right:
                self.wall_follow_side = "left"
                self.last_wall_distance = left
            else:
                self.wall_follow_side = "right"
                self.last_wall_distance = right
        
        # Get distance to followed wall
        wall_distance = (left if self.wall_follow_side == "left" else right)
        self.last_wall_distance = wall_distance
        
        # PID-like control to maintain wall distance
        distance_error = wall_distance - self.wall_distance_target
        steering = np.clip(distance_error * 0.3, -1.0, 1.0)
        
        # If wall is on right, positive steering = right turn
        if self.wall_follow_side == "left":
            steering = -steering
        
        # Forward speed based on front obstacle
        forward_speed = 0.5
        if front < self.safe_distance:
            forward_speed = max(0.0, (front - self.critical_distance) / 
                              (self.safe_distance - self.critical_distance)) * 0.3
        
        confidence = 0.8 if wall_distance < 2.0 else 0.5
        
        return AvoidanceCommand(
            linear_velocity=forward_speed,
            angular_velocity=steering,
            strategy_used=AvoidanceStrategy.WALL_FOLLOWING,
            obstacle_detected=obstacle_detected,
            confidence=confidence
        )
    
    def _random_walk(self, distances: Dict[str, float]) -> AvoidanceCommand:
        """
        Random walk strategy: move forward until obstacle, then turn randomly.
        
        Args:
            distances: Smoothed sensor distances
        
        Returns:
            Control command
        """
        front = distances['front']
        obstacle_detected = front < self.safe_distance
        
        # Check if time to change direction
        elapsed = time.time() - self.random_walk_last_change
        if obstacle_detected or elapsed > self.random_walk_duration:
            # Choose new random direction
            self.random_walk_direction = np.random.uniform(-90, 90)
            self.random_walk_last_change = time.time()
            self.avoidance_maneuvers += 1
        
        # Convert direction to motor command
        angular_velocity = np.clip(self.random_walk_direction / 90, -1.0, 1.0)
        linear_velocity = 0.0 if obstacle_detected else 0.4
        
        confidence = 0.5  # Random walk is less confident
        
        return AvoidanceCommand(
            linear_velocity=linear_velocity,
            angular_velocity=angular_velocity,
            strategy_used=AvoidanceStrategy.RANDOM_WALK,
            obstacle_detected=obstacle_detected,
            confidence=confidence
        )
    
    def _potential_field(self, distances: Dict[str, float]) -> AvoidanceCommand:
        """
        Potential field method: obstacles repel, goal attracts.
        
        Args:
            distances: Smoothed sensor distances
        
        Returns:
            Control command
        """
        front = distances['front']
        left = distances['left']
        right = distances['right']
        
        # Repulsive forces from obstacles
        # Stronger repulsion when closer to obstacle
        front_repulsion = -1.0 / max(front, 0.1) if front < self.safe_distance else 0
        left_repulsion = -1.0 / max(left, 0.1) if left < self.safe_distance else 0
        right_repulsion = 1.0 / max(right, 0.1) if right < self.safe_distance else 0  # Opposite sign
        
        # Normalize repulsions
        front_repulsion = np.clip(front_repulsion, -1.0, 1.0)
        lateral_repulsion = np.clip(left_repulsion + right_repulsion, -1.0, 1.0)
        
        # Attractive force toward goal (forward)
        attraction = 0.6
        
        # Combine forces
        linear_velocity = attraction + front_repulsion * 0.5
        angular_velocity = lateral_repulsion
        
        linear_velocity = np.clip(linear_velocity, -1.0, 1.0)
        angular_velocity = np.clip(angular_velocity, -1.0, 1.0)
        
        obstacle_detected = front < self.safe_distance
        confidence = 0.7
        
        return AvoidanceCommand(
            linear_velocity=linear_velocity,
            angular_velocity=angular_velocity,
            strategy_used=AvoidanceStrategy.POTENTIAL_FIELD,
            obstacle_detected=obstacle_detected,
            confidence=confidence
        )
    
    def _bug_algorithm(self, distances: Dict[str, float]) -> AvoidanceCommand:
        """
        BUG algorithm: go toward goal, if blocked then follow wall.
        
        Args:
            distances: Smoothed sensor distances
        
        Returns:
            Control command
        """
        front = distances['front']
        obstacle_detected = front < self.safe_distance
        
        if obstacle_detected:
            # Follow wall until can go to goal again
            self.bug_state = "following_wall"
            return self._wall_following(distances)
        else:
            # Go toward goal
            self.bug_state = "going_to_goal"
            return AvoidanceCommand(
                linear_velocity=0.5,
                angular_velocity=0.0,
                strategy_used=AvoidanceStrategy.BUG_ALGORITHM,
                obstacle_detected=False,
                confidence=0.9
            )
    
    def _hybrid_strategy(self, distances: Dict[str, float]) -> AvoidanceCommand:
        """
        Hybrid strategy: switch between strategies based on situation.
        
        Args:
            distances: Smoothed sensor distances
        
        Returns:
            Control command
        """
        front = distances['front']
        left = distances['left']
        right = distances['right']
        
        # Strategy selection logic
        if front < self.critical_distance * 1.5:
            # Very close obstacle, use wall following
            if self.strategy != AvoidanceStrategy.WALL_FOLLOWING:
                self.set_strategy(AvoidanceStrategy.WALL_FOLLOWING)
                self.strategy_changes += 1
        elif (left > self.safe_distance and right > self.safe_distance):
            # Open space, use potential field
            if self.strategy != AvoidanceStrategy.POTENTIAL_FIELD:
                self.set_strategy(AvoidanceStrategy.POTENTIAL_FIELD)
                self.strategy_changes += 1
        
        # Execute current strategy
        return self.calculate_avoidance(
            ObstacleData(front, left, right, distances.get('rear'), time.time())
        )
    
    def set_strategy(self, strategy: AvoidanceStrategy) -> None:
        """
        Change avoidance strategy.
        
        Args:
            strategy: New strategy to use
        """
        old_strategy = self.strategy
        self.strategy = strategy
        self.strategy_changes += 1
        
        logging.info(f"Avoidance strategy changed: {old_strategy.value} → "
                    f"{strategy.value}")
        self.logger.log_mission_event("Obstacle Avoidance",
                                      f"Strategy: {old_strategy.value} → "
                                      f"{strategy.value}")
        
        # Reset strategy-specific state
        self.last_wall_distance = None
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Get avoidance performance metrics.
        
        Returns:
            Dictionary with metrics
        """
        return {
            'collision_count': float(self.collision_count),
            'avoidance_maneuvers': float(self.avoidance_maneuvers),
            'strategy_changes': float(self.strategy_changes),
            'current_strategy': self.strategy.value,
            'current_wall_follow_side': self.wall_follow_side,
            'wall_distance_target': self.wall_distance_target,
        }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.collision_count = 0
        self.avoidance_maneuvers = 0
        self.strategy_changes = 0
        logging.info("ObstacleAvoider metrics reset")
