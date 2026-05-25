"""
Test Module for Red Line Tracking Feature
Tests red line detection and motor response without running main robot system.

"""

import cv2
import numpy as np
from src.utils.control_utils import set_motors_direction

# ============= Camera Configuration =============
# FIX #5: Đồng bộ với cấu hình thực tế của line_tracker.py
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480  # Sửa từ 360 thành 480
FRAME_CENTER_X = CAMERA_WIDTH // 2   # 320
FRAME_CENTER_Y = CAMERA_HEIGHT // 2  # 240

# ============= HSV Color Range for Red Detection =============
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# ============= Tracking Parameters =============
MIN_CONTOUR_AREA = 500
DEVIATION_THRESHOLD = 80   # pixel — Ngưỡng lệch ngang để bắt đầu bo cua gắt
ANGLE_THRESHOLD = 15       # độ — Nếu đường line nghiêng vượt ngưỡng thì điều chỉnh hướng
MOTOR_SPEED = 0.1
DISPLAY_THICKNESS = 2
DISPLAY_COLOR = (0, 0, 255)  # Màu đỏ dạng BGR


def setup_camera() -> cv2.VideoCapture:
    """
    Initialize và configure camera.
    
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
    Detect red line và trả về contour info, góc lệch và độ lệch pixel.
    
    FIX #6a: Chuẩn hóa angle về khoảng [-45, 45] dùng cấu trúc if/elif loại trừ
    để tránh việc một giá trị góc bị biến đổi lặp lại ở nhiều khối logic độc lập.
    
    Returns:
        Tuple (largest_contour, angle_deg, error_x)
        Tất cả là None nếu không phát hiện được đường line.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Tạo mask nhận diện màu đỏ kép (do dải màu đỏ nằm ở 2 đầu thanh HSV)
    red_mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
    red_mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
    red_mask = red_mask1 | red_mask2
    
    # Morphological filtering để khử nhiễu môi trường
    kernel = np.ones((5, 5), np.uint8)
    red_mask = cv2.erode(red_mask, kernel, iterations=1)
    red_mask = cv2.dilate(red_mask, kernel, iterations=2)
    
    # Tìm contours đường line
    contours, _ = cv2.findContours(red_mask.copy(), cv2.RETR_TREE, 
                                   cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None, None, None
    
    # Lấy contour lớn nhất để loại bỏ các điểm nhiễu đỏ nhỏ xung quanh
    largest_contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest_contour) < MIN_CONTOUR_AREA:
        return None, None, None
    
    # Tính toán hình chữ nhật bao quanh nhỏ nhất (Rotated Rectangle)
    min_rect = cv2.minAreaRect(largest_contour)
    (x_center, y_center), (width, height), angle = min_rect
    
    if width == 0 or height == 0:
        return largest_contour, 0, int(x_center - FRAME_CENTER_X)
        
    # FIX #6a: Áp dụng if/elif loại trừ tuần tự để chuẩn hóa góc nghiêng thực tế
    if angle < -45:
        angle = 90 + angle
    elif width < height and angle > 0:
        angle = (90 - angle) * -1
    elif width > height and angle < 0:
        angle = 90 + angle
    
    # Giới hạn biên an toàn tuyệt đối cho giá trị góc nghiêng
    angle = max(-45, min(45, angle))
    
    # Tính khoảng cách lệch pixel giữa tâm vật thể và tâm khung hình hình học
    error_x = int(x_center - FRAME_CENTER_X)
    
    return largest_contour, int(angle), error_x


def decide_motor_command(error_x: int, angle: int) -> str:
    """
    FIX #6b: Hàm bổ sung quyết định hướng đi dựa trên cả error_x VÀ angle.
    Giúp tối ưu hóa chuyển động, tránh hiện tượng giật lắc khi bám vạch.
    
    Returns:
        String định danh lệnh di chuyển ('go_forward', 'rotate_left', v.v.)
    """
    abs_error = abs(error_x)
    abs_angle = abs(angle)

    # 1. Đi thẳng: Nếu nằm giữa tâm khung hình và góc nghiêng nhỏ
    if abs_error <= DEVIATION_THRESHOLD and abs_angle <= ANGLE_THRESHOLD:
        return 'go_forward'

    # 2. Lệch ngang nghiêm trọng: Ưu tiên xoay tại chỗ để đưa line về tâm ảnh
    if abs_error > DEVIATION_THRESHOLD:
        return 'rotate_left' if error_x < 0 else 'rotate_right'

    # 3. Lệch tâm nhỏ nhưng line bị chéo: Điều hướng rẽ nhẹ (Turn) góc cua mượt
    if angle < -ANGLE_THRESHOLD:
        return 'turn_left'
    if angle > ANGLE_THRESHOLD:
        return 'turn_right'

    return 'go_forward'


def visualize_detection(frame: np.ndarray, contour: np.ndarray, 
                        angle: int, error_x: int, motor_cmd: str) -> np.ndarray:
    """
    Vẽ trực quan hóa vạch kẻ, tọa độ tâm và lệnh điều khiển lên màn hình kiểm thử.
    """
    # Vẽ đường thẳng trung tâm ảnh (Green) làm mốc tham chiếu
    cv2.line(frame, (FRAME_CENTER_X, 0), (FRAME_CENTER_X, CAMERA_HEIGHT), (0, 255, 0), 1)
    
    if contour is None:
        cv2.putText(frame, "No line detected", (10, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return frame
    
    # Vẽ Bounding Box bao quanh vạch đỏ phát hiện được
    min_rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(min_rect)
    box = np.intp(box)
    cv2.drawContours(frame, [box], 0, DISPLAY_COLOR, DISPLAY_THICKNESS)
    
    # Định vị tọa độ điểm trung tâm của cấu trúc vạch
    cx = int(min_rect[0][0])
    cy = int(min_rect[0][1])
    cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)
    cv2.line(frame, (cx, FRAME_CENTER_Y - 25), (cx, FRAME_CENTER_Y + 25), (255, 0, 0), DISPLAY_THICKNESS)
    
    # Hiển thị các thông số dữ liệu thời gian thực
    cv2.putText(frame, f"Angle: {angle} deg  Error: {error_x} px", (10, 40), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, DISPLAY_COLOR, 2)
    cv2.putText(frame, f"CMD: {motor_cmd}", (10, 75), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
    return frame


def main() -> None:
    """Main test loop."""
    camera = None
    try:
        camera = setup_camera()
        
        print("Starting red line tracking feature test...")
        print(f"Resolution configured: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
        print("Press 'q' on the CV window to safely terminate.\n")
        
        while True:
            ret, frame = camera.read()
            if not ret:
                print("Error: Could not read a frame from the webcam.")
                break
            
            # Thực hiện tác vụ xử lý ảnh nguồn
            contour, angle, error_x = detect_red_line(frame)
            
            # FIX #6b: Phân luồng tính toán tập lệnh motor dựa trên sự kết hợp trạng thái
            if contour is not None:
                motor_cmd = decide_motor_command(error_x, angle)
                # Thực hiện truyền tín hiệu điều khiển trực tiếp tới Driver phần cứng
                set_motors_direction(motor_cmd, MOTOR_SPEED, 0, 0)
                print(f"Tracking -> Angle: {angle:3d}° | Error_x: {error_x:4d}px | Executed: {motor_cmd}")
            else:
                # Nếu mất dấu vạch đỏ -> Thực hiện quay xe tại chỗ ở tốc độ kiểm thử để quét tìm lại
                motor_cmd = "rotate_left (searching)"
                set_motors_direction('rotate_left', MOTOR_SPEED, 0, 0)
                print("Status -> No line detected! Robot is searching...")
            
            # Hiển thị trực quan dữ liệu lên màn hình GUI kết quả
            frame = visualize_detection(frame, contour, angle, error_x if error_x else 0, motor_cmd)
            cv2.imshow("Red Line Tracking Test", frame)
            
            # Ngắt chương trình an toàn
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\nTest tracking sequence completed by user request.")
                break
                
    except RuntimeError as e:
        print(f"Fatal driver execution error: {e}")
    except Exception as e:
        print(f"Unexpected system interruption occurred: {e}")
    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()
        print("System cleanup completed. All windows and hardware instances released.")


if __name__ == "__main__":
    main()