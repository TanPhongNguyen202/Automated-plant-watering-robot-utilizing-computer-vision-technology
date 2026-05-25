"""
Red Line Tracking Module
Detects and follows a red line using computer vision and controls robot movement.
Uses PID control for smooth line following instead of simple ON/OFF logic.
"""

import cv2
import numpy as np
from src.utils.control_utils import set_motors_direction
from src.control.pid_controller import PIDController

# ============= Camera Configuration =============
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_CENTER_X = FRAME_WIDTH // 2
FRAME_CENTER_Y = FRAME_HEIGHT // 2

# ============= HSV Color Range for Red Detection =============
# Red color in HSV has two ranges due to color wrap-around at 180°
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# ============= Line Tracking Parameters =============
MIN_CONTOUR_AREA = 1000
DEVIATION_THRESHOLD = 150  # Pixels from center for significant deviation
MOTOR_SPEED = 0.1

# ============= PID Controller Parameters =============
# P: Proportional gain - controls how aggressively robot responds to error
# I: Integral gain - compensates for steady-state error
# D: Derivative gain - provides damping to prevent oscillation
PID_KP = 0.008  # Proportional gain (default: 0.008)
PID_KI = 0.001  # Integral gain (default: 0.001)
PID_KD = 0.003  # Derivative gain (default: 0.003)
PID_MAX_OUTPUT = 0.5  # Max turning speed adjustment

# ============= Camera Configuration =============
# If camera is mounted facing downward (common for line followers),
# line below center = robot approaching line (should move forward)
# line above center = robot passed line (should turn to find it)
CAMERA_FACING_DOWN = True  # Set to False if camera faces forward

# ============= Display Configuration =============
DISPLAY_TEXT_COLOR = (255, 255, 255)
DISPLAY_FONT = cv2.FONT_HERSHEY_SIMPLEX
DISPLAY_FONT_SCALE = 0.5


class RedLineTracker:
    """
    Handles red line detection and robot line-following control.
    """
    
    def __init__(self, camera_index: int = CAMERA_INDEX):
        """
        Initialize the red line tracker with PID control.
        
        Args:
            camera_index: Index of the camera device (default 0)
        """
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open camera device")
        
        # Initialize PID controller for smooth line following
        # Error input: deviation from center (in pixels)
        # Output: turning speed adjustment (normalized -1.0 to 1.0)
        self.pid = PIDController(kp=PID_KP, ki=PID_KI, kd=PID_KD)
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Convert frame to HSV and create mask for red color.
        Includes morphological filtering to reduce noise.
        
        Args:
            frame: Input frame in BGR format
        
        Returns:
            Binary mask of red pixels (cleaned with morphological operations)
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
        mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
        mask = mask1 | mask2
        
        # Apply morphological operations to reduce noise
        # Erode removes small noise particles
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        # Dilate restores the size of remaining objects
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        return mask
    
    def analyze_contours(self, mask: np.ndarray) -> tuple:
        """
        Find contours and calculate deviation from frame center.
        
        Args:
            mask: Binary mask of red pixels
        
        Returns:
            Tuple of (detected: bool, deviation_x: int, deviation_y: int, 
                     contours: list, bounding_box: tuple)
        """
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, 
                                       cv2.CHAIN_APPROX_SIMPLE)
        
        deviation_x = deviation_y = 0
        bounding_box = (0, 0, 0, 0)
        detected = False
        
        # Find the largest contour
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            
            if area > MIN_CONTOUR_AREA:
                x, y, w, h = cv2.boundingRect(largest_contour)
                bounding_box = (x, y, w, h)
                
                # Calculate center point
                center_x = x + w // 2
                center_y = y + h // 2
                
                # Calculate deviation from frame center
                deviation_x = center_x - FRAME_CENTER_X
                deviation_y = center_y - FRAME_CENTER_Y
                detected = True
        
        return detected, deviation_x, deviation_y, contours, bounding_box
    
    def control_robot_movement(self, detected: bool, deviation_x: int, 
                              deviation_y: int) -> None:
        """
        Control robot movement based on line detection using PID control.
        
        PID output adjusts motor speeds proportionally:
        - Negative PID output: turn left (reduce left motor speed, increase right)
        - Positive PID output: turn right (increase left motor speed, reduce right)
        - Zero PID output: go straight
        
        Args:
            detected: Whether the red line was detected
            deviation_x: Horizontal deviation from frame center (pixels)
            deviation_y: Vertical deviation from frame center (pixels)
        """
        if not detected:
            # No line detected, search for it by rotating
            set_motors_direction('rotate_left', MOTOR_SPEED, 0, 0)
            return
        
        # For camera facing down: positive deviation_y means line is approaching
        # For camera facing forward: logic would be inverted
        # Use PID to calculate smooth turning adjustment based on horizontal error
        pid_output = self.pid.calculate(error=deviation_x)
        
        # Clamp PID output to reasonable range (acts as steering angle)
        pid_output = max(-PID_MAX_OUTPUT, min(PID_MAX_OUTPUT, pid_output))
        
        # Determine movement based on vertical position
        if CAMERA_FACING_DOWN and deviation_y > 0:
            # Line is below center (approaching) - move forward with PID-adjusted steering
            # pid_output acts as steering angle (theta parameter)
            set_motors_direction('go_forward', MOTOR_SPEED, 0, pid_output)
        else:
            # Line is above center or camera facing forward - rotate to align
            # Pure rotation with PID-adjusted intensity
            rotation_speed = MOTOR_SPEED * abs(pid_output)
            if pid_output < 0:
                set_motors_direction('rotate_left', rotation_speed, 0, 0)
            else:
                set_motors_direction('rotate_right', rotation_speed, 0, 0)
    
    def display_info(self, frame: np.ndarray, detected: bool, 
                    deviation_x: int, deviation_y: int) -> None:
        """
        Display detection info on frame.
        
        Args:
            frame: Frame to draw on
            detected: Whether line was detected
            deviation_x: Horizontal deviation
            deviation_y: Vertical deviation
        """
        status_text = "Line Detected" if detected else "No Line"
        cv2.putText(frame, f"Status: {status_text}", (10, 25), 
                   DISPLAY_FONT, DISPLAY_FONT_SCALE, DISPLAY_TEXT_COLOR, 1)
        cv2.putText(frame, f"Deviation: X={deviation_x} Y={deviation_y}", 
                   (10, 45), DISPLAY_FONT, DISPLAY_FONT_SCALE, 
                   DISPLAY_TEXT_COLOR, 1)
    
    def run(self) -> None:
        """Main loop for red line tracking."""
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Error: Failed to read frame from camera")
                    break
                
                # Detect red line
                mask = self.process_frame(frame)
                detected, dev_x, dev_y, _, _ = self.analyze_contours(mask)
                
                # Control robot based on detection
                self.control_robot_movement(detected, dev_x, dev_y)
                
                # Display information
                self.display_info(frame, detected, dev_x, dev_y)
                cv2.imshow("Red Line Tracking", frame)
                
                # Exit on 'q' key press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Release camera and close windows."""
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        tracker = RedLineTracker()
        tracker.run()
    except RuntimeError as e:
        print(f"Fatal error: {e}")
