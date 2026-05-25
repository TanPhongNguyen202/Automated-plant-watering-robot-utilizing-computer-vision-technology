"""
Advanced Line Following Controller with PID
Implements professional-grade line tracking using PID control with adaptive tuning.
Supports multiple line-following strategies and cross-track error minimization.
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from enum import Enum
import logging
import time

from src.control.pid_controller import PIDController
from src.utils.circular_buffer import CircularBuffer
from src.utils.lifecycle_logger import LifecycleLogger


class LineFollowingStrategy(Enum):
    """Line following strategy modes."""
    AGGRESSIVE = "aggressive"          # Fast response, high oscillation
    BALANCED = "balanced"              # Medium response, stable
    CONSERVATIVE = "conservative"      # Smooth response, slow
    ADAPTIVE = "adaptive"              # Auto-tune based on line quality


@dataclass
class LineDetectionResult:
    """Container for line detection results."""
    detected: bool
    center_x: float
    center_y: float
    width: float
    angle: float  # Line orientation in degrees
    area: float
    quality_score: float  # 0-100, higher is better
    contours: List[np.ndarray]
    bounding_box: Tuple[int, int, int, int]


@dataclass
class ControlOutput:
    """Motor control output from line follower."""
    velocity_forward: float  # -1.0 to 1.0
    angular_velocity: float  # -1.0 to 1.0 (rotation)
    confidence: float        # 0-1.0 (control confidence)


class LineFollower:
    """
    Professional line following controller with PID-based cross-track error control.
    
    Supports:
    - Multiple detection strategies (HSV ranges, edge detection, etc.)
    - PID-based heading control
    - Adaptive tuning based on line quality
    - Performance metrics and logging
    - Obstacle detection during line following
    """
    
    def __init__(self, 
                 frame_width: int = 640,
                 frame_height: int = 480,
                 strategy: LineFollowingStrategy = LineFollowingStrategy.BALANCED,
                 logger: Optional[LifecycleLogger] = None):
        """
        Initialize line follower.
        
        Args:
            frame_width: Camera frame width in pixels
            frame_height: Camera frame height in pixels
            strategy: Line following strategy to use
            logger: Optional lifecycle logger for metrics
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.frame_center_x = frame_width / 2
        self.frame_center_y = frame_height / 2
        self.strategy = strategy
        self.logger = logger or LifecycleLogger()
        
        # ========== Detection Configuration ==========
        # HSV ranges for red line (two ranges due to color wrap)
        self.lower_red1 = np.array([0, 120, 70])
        self.upper_red1 = np.array([10, 255, 255])
        self.lower_red2 = np.array([170, 120, 70])
        self.upper_red2 = np.array([180, 255, 255])
        
        # Detection thresholds
        self.min_contour_area = 500  # Minimum line area
        self.quality_threshold = 30.0  # Minimum quality for valid detection
        
        # ========== PID Controllers ==========
        self.pid_strategies: Dict[LineFollowingStrategy, Dict[str, float]] = {
            LineFollowingStrategy.AGGRESSIVE: {
                'kp': 1.5, 'ki': 0.3, 'kd': 0.8
            },
            LineFollowingStrategy.BALANCED: {
                'kp': 0.8, 'ki': 0.15, 'kd': 0.4
            },
            LineFollowingStrategy.CONSERVATIVE: {
                'kp': 0.4, 'ki': 0.08, 'kd': 0.2
            }
        }
        
        # Initialize PID for cross-track error (lateral position)
        self._init_pid_controller(strategy)
        
        # ========== State Tracking ==========
        self.last_detection_time = time.time()
        self.detection_history = CircularBuffer(max_size=30)
        self.cross_track_error_history = CircularBuffer(max_size=100)
        
        # Performance metrics
        self.total_frames = 0
        self.detection_count = 0
        self.missed_frames = 0
        
        logging.info(f"LineFollower initialized: {frame_width}x{frame_height}, "
                    f"strategy={strategy.value}")
    
    def _init_pid_controller(self, strategy: LineFollowingStrategy) -> None:
        """Initialize PID controller with strategy-specific gains."""
        gains = self.pid_strategies.get(
            strategy, 
            self.pid_strategies[LineFollowingStrategy.BALANCED]
        )
        
        self.pid_cross_track = PIDController(
            kp=gains['kp'],
            ki=gains['ki'],
            kd=gains['kd'],
            output_limits=(-1.0, 1.0),
            name="cross_track_error"
        )
        
        logging.info(f"PID initialized: Kp={gains['kp']}, Ki={gains['ki']}, "
                    f"Kd={gains['kd']}")
    
    def detect_line(self, frame: np.ndarray) -> LineDetectionResult:
        """
        Detect red line in frame using HSV color detection.
        
        Args:
            frame: Input frame in BGR format
        
        Returns:
            LineDetectionResult with detection status and metrics
        """
        self.total_frames += 1
        
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Create mask for red line
        mask1 = cv2.inRange(hsv, self.lower_red1, self.upper_red1)
        mask2 = cv2.inRange(hsv, self.lower_red2, self.upper_red2)
        mask = mask1 | mask2
        
        # Morphological operations to clean mask
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, 
                                       cv2.CHAIN_APPROX_SIMPLE)
        
        # Initialize default result (not detected)
        result = LineDetectionResult(
            detected=False,
            center_x=self.frame_center_x,
            center_y=self.frame_center_y,
            width=0,
            angle=0,
            area=0,
            quality_score=0,
            contours=contours,
            bounding_box=(0, 0, 0, 0)
        )
        
        if not contours:
            self.missed_frames += 1
            return result
        
        # Find largest contour (most likely the line)
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        if area < self.min_contour_area:
            self.missed_frames += 1
            return result
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Calculate line properties
        center_x = x + w / 2
        center_y = y + h / 2
        
        # Fit line to get orientation
        line_angle = self._calculate_line_angle(largest_contour)
        
        # Calculate quality score (based on contour regularity)
        quality = self._calculate_detection_quality(largest_contour, area)
        
        if quality < self.quality_threshold:
            self.missed_frames += 1
            return result
        
        # Valid detection
        self.detection_count += 1
        self.last_detection_time = time.time()
        
        result.detected = True
        result.center_x = center_x
        result.center_y = center_y
        result.width = w
        result.angle = line_angle
        result.area = area
        result.quality_score = quality
        result.bounding_box = (x, y, w, h)
        
        self.detection_history.append(result)
        
        return result
    
    def _calculate_line_angle(self, contour: np.ndarray) -> float:
        """
        Calculate line orientation angle.
        
        Args:
            contour: Contour points
        
        Returns:
            Angle in degrees (-90 to 90)
        """
        if len(contour) < 5:
            return 0.0
        
        try:
            ellipse = cv2.fitEllipse(contour)
            angle = ellipse[2]
            # Normalize to -90 to 90
            if angle > 90:
                angle -= 180
            return angle
        except:
            return 0.0
    
    def _calculate_detection_quality(self, contour: np.ndarray, 
                                     area: float) -> float:
        """
        Calculate detection quality score (0-100).
        
        Factors:
        - Contour regularity (circularity)
        - Contour completeness
        - Area consistency
        
        Args:
            contour: Contour points
            area: Contour area
        
        Returns:
            Quality score 0-100
        """
        # Circularity: 4π*Area / Perimeter²
        perimeter = cv2.arcLength(contour, False)
        if perimeter == 0:
            return 0.0
        
        circularity = 4 * np.pi * area / (perimeter ** 2)
        
        # Contour points ratio
        point_density = min(len(contour) / 50, 1.0)  # Normalized
        
        # Quality is combination of circularity and point density
        quality = (circularity * 0.6 + point_density * 0.4) * 100
        
        return min(quality, 100.0)
    
    def calculate_control(self, detection: LineDetectionResult, 
                         forward_speed: float = 0.5) -> ControlOutput:
        """
        Calculate motor control outputs using PID controller.
        
        Args:
            detection: Line detection result
            forward_speed: Desired forward speed (0-1)
        
        Returns:
            ControlOutput with velocity commands
        """
        if not detection.detected:
            # No line detected, spin to find it
            return ControlOutput(
                velocity_forward=0.0,
                angular_velocity=0.3,  # Rotate to search
                confidence=0.0
            )
        
        # Calculate cross-track error (deviation from center)
        cross_track_error = detection.center_x - self.frame_center_x
        
        # Store for metrics
        self.cross_track_error_history.append(cross_track_error)
        
        # Apply PID control
        angular_correction = self.pid_cross_track.update(cross_track_error)
        
        # Reduce forward speed if confidence is low
        confidence = min(detection.quality_score / self.quality_threshold, 1.0)
        actual_forward_speed = forward_speed * confidence
        
        # If line is significantly off-center, prioritize steering
        if abs(angular_correction) > 0.5:
            actual_forward_speed *= 0.7  # Slow down during sharp turns
        
        control = ControlOutput(
            velocity_forward=np.clip(actual_forward_speed, -1.0, 1.0),
            angular_velocity=angular_correction,
            confidence=confidence
        )
        
        return control
    
    def set_strategy(self, strategy: LineFollowingStrategy) -> None:
        """
        Change line following strategy dynamically.
        
        Args:
            strategy: New strategy to use
        """
        self.strategy = strategy
        self._init_pid_controller(strategy)
        logging.info(f"Strategy changed to: {strategy.value}")
        self.logger.log_mission_event("Line Following", 
                                      f"Strategy changed to {strategy.value}")
    
    def adapt_strategy(self, recent_quality: float) -> None:
        """
        Automatically adjust strategy based on line quality.
        
        Args:
            recent_quality: Recent average detection quality (0-100)
        """
        if recent_quality < 30:
            # Poor detection, use conservative strategy
            self.set_strategy(LineFollowingStrategy.CONSERVATIVE)
        elif recent_quality < 60:
            # Moderate detection, use balanced strategy
            self.set_strategy(LineFollowingStrategy.BALANCED)
        elif self.strategy != LineFollowingStrategy.ADAPTIVE:
            # Good detection, can be aggressive
            self.set_strategy(LineFollowingStrategy.AGGRESSIVE)
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Get current performance metrics.
        
        Returns:
            Dictionary with performance stats
        """
        detection_rate = (self.detection_count / max(self.total_frames, 1)) * 100
        
        metrics = {
            'total_frames': float(self.total_frames),
            'detection_rate': detection_rate,
            'detection_count': float(self.detection_count),
            'missed_frames': float(self.missed_frames),
        }
        
        if self.cross_track_error_history.get_size() > 0:
            cte_array = self.cross_track_error_history.get_numpy_array()
            metrics.update({
                'cte_avg': float(np.mean(np.abs(cte_array))),
                'cte_std': float(np.std(cte_array)),
                'cte_max': float(np.max(np.abs(cte_array))),
            })
        
        pid_stats = self.pid_cross_track.get_statistics()
        metrics.update({
            'pid_updates': float(pid_stats['update_count']),
            'pid_last_output': float(pid_stats['last_output']),
        })
        
        return metrics
    
    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        self.total_frames = 0
        self.detection_count = 0
        self.missed_frames = 0
        self.pid_cross_track.reset()
        self.detection_history = CircularBuffer(max_size=30)
        self.cross_track_error_history = CircularBuffer(max_size=100)
        logging.info("LineFollower metrics reset")
