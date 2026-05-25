"""
Test Module for Red Line Tracking Feature
Tests basic red line detection and motor response without running main robot system.
"""

import cv2
import numpy as np
from src.utils.control_utils import set_motors_direction

# ============= Camera Configuration =============
# IMPORTANT: Must match line_tracker.py resolution for consistent testing
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480  # Changed from 360 to match line_tracker.py FRAME_HEIGHT
FRAME_CENTER_X = CAMERA_WIDTH // 2
FRAME_CENTER_Y = CAMERA_HEIGHT // 2

# ============= HSV Color Range for Red Detection =============
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# ============= Tracking Parameters =============
MIN_CONTOUR_AREA = 500
DEVIATION_THRESHOLD = 150
MOTOR_SPEED = 0.1
DISPLAY_THICKNESS = 2
DISPLAY_COLOR = (0, 0, 255)  # Red in BGR


def setup_camera() -> cv2.VideoCapture:
    """
    Initialize and configure camera.
    
    Returns:
        Configured video capture object
    
    Raises:
        RuntimeError: If camera cannot be opened
    """
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    
    if not camera.isOpened():
        raise RuntimeError("Error: Could not open the webcam.")
    
    return camera


def detect_red_line(frame: np.ndarray) -> tuple:
    """
    Detect red line in frame and return contour information.
    
    Args:
        frame: Input frame in BGR format
    
    Returns:
        Tuple of (largest_contour, angle, error_x)
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Create red masks
    red_mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
    red_mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
    red_mask = red_mask1 | red_mask2
    
    # Find contours
    contours, _ = cv2.findContours(red_mask.copy(), cv2.RETR_TREE, 
                                    cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None, None, None
    
    # Get largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Get rotated rectangle
    min_rect = cv2.minAreaRect(largest_contour)
    (x_center, y_center), (width, height), angle = min_rect
    
    # Normalize angle to [-45, 45] range
    # Use elif to prevent multiple transformations on same angle (edge case fix)
    if angle < -45:
        # Rotate frame reference by 90°
        angle = 90 + angle
    elif width < height and angle > 0:
        # Line is more vertical than horizontal
        angle = (90 - angle) * -1
    elif width > height and angle < 0:
        # Line is more horizontal than vertical
        angle = 90 + angle
    # else: angle is already in valid range [-45, 45]
    
    # Calculate horizontal error
    error_x = int(x_center - FRAME_CENTER_X)
    
    return largest_contour, int(angle), error_x


def visualize_detection(frame: np.ndarray, contour: np.ndarray, 
                       angle: int, error_x: int) -> np.ndarray:
    """
    Draw detection visualization on frame.
    
    Args:
        frame: Input frame
        contour: Detected contour
        angle: Line angle
        error_x: Horizontal error
    
    Returns:
        Frame with visualization
    """
    if contour is None:
        return frame
    
    # Draw bounding box
    min_rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(min_rect)
    box = np.intp(box)
    cv2.drawContours(frame, [box], 0, DISPLAY_COLOR, DISPLAY_THICKNESS)
    
    # Draw center line
    cv2.line(frame, (int(min_rect[0][0]), 200), 
            (int(min_rect[0][0]), 250), (255, 0, 0), DISPLAY_THICKNESS)
    
    # Display text info
    cv2.putText(frame, f"Angle: {angle}", (10, 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, DISPLAY_COLOR, 2)
    cv2.putText(frame, f"Error: {error_x}", (10, 80), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    return frame


def main() -> None:
    """Main test loop."""
    try:
        camera = setup_camera()
        
        print("Starting red line detection test...")
        print("Press 'q' to quit\n")
        
        while True:
            ret, frame = camera.read()
            if not ret:
                print("Error: Could not read a frame from the webcam.")
                break
            
            # Detect red line
            contour, angle, error_x = detect_red_line(frame)
            
            # Display results
            frame = visualize_detection(frame, contour, angle, error_x)
            cv2.imshow("Red Line Tracking Test", frame)
            
            # Log detection status
            if contour is not None:
                print(f"Line detected - Angle: {angle}°, Error: {error_x}px")
            else:
                print("No line detected")
            
            # Exit condition
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\nTest completed.")
                break
    
    except RuntimeError as e:
        print(f"Fatal error: {e}")
    
    finally:
        camera.release()
        cv2.destroyAllWindows()
