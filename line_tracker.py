"""
Red Line Tracking - Hybrid Version
Combines advanced geometric detection (Rotated Rect & Angle) with smooth PID control.
Eliminates discrete transitions to provide fluid line-following behavior.
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
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# ============= Line Tracking Parameters =============
MIN_CONTOUR_AREA = 800  # Cân bằng giữa lọc nhiễu và độ nhạy xa
MOTOR_SPEED = 0.15

# ============= Hybrid PID Controller Parameters =============
# Vì sai số (Error) giờ là sự kết hợp giữa Pixel và Độ (Angle), 
# các tham số KP, KI, KD cần được tinh chỉnh lại cho phù hợp.
PID_KP = 0.006       # Phản ứng với sai số hiện tại
PID_KI = 0.0005      # Khử sai số tích lũy ở các đoạn cua dài
PID_KD = 0.002       # Giảm chấn, chống lắc đuôi robot
PID_MAX_OUTPUT = 0.6 # Giới hạn góc lái tối đa

# Trọng số kết hợp: Sai số tổng hợp = Error_X + (Angle * WEIGHT)
# Giúp robot vừa muốn về tâm ảnh, vừa muốn bẻ lái theo hướng vạch chỉ
ANGLE_WEIGHT = 4.0   


class RedLineTracker:
    """
    Robot line-following sử dụng công nghệ lai: 
    Quét góc nâng cao + Điều khiển PID mượt mà.
    """
    
    def __init__(self, camera_index: int = CAMERA_INDEX):
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        
        if not self.cap.isOpened():
            raise RuntimeError("Không thể kết nối với Camera")
        
        # Khởi tạo bộ điều khiển PID
        self.pid = PIDController(kp=PID_KP, ki=PID_KI, kd=PID_KD)
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Lọc màu đỏ và áp dụng bộ lọc hình thái học để giảm nhiễu."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
        mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
        mask = mask1 | mask2
        
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        return mask
    
    def analyze_line_geometry(self, mask: np.ndarray) -> tuple:
        """
        Phân tích hình học nâng cao sử dụng Rotated Bounding Box.
        
        Returns:
            Tuple (detected, error_x, angle, largest_contour, min_rect)
        """
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return False, 0, 0, None, None
            
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        if area < MIN_CONTOUR_AREA:
            return False, 0, 0, None, None
            
        # Tính toán Bounding Box xoay thay vì Box chữ nhật đứng
        min_rect = cv2.minAreaRect(largest_contour)
        (x_center, y_center), (width, height), angle = min_rect
        
        if width == 0 or height == 0:
            return False, 0, 0, None, None

        # --- Chuẩn hóa góc nghiêng của OpenCV về khoảng (-45, 45] ---
        # Quy ước: 0 là thẳng đứng, >0 là nghiêng phải, <0 là nghiêng trái
        if width < height:
            normalized_angle = angle + 90
        else:
            normalized_angle = angle
            
        # Ép góc vào khoảng an toàn
        normalized_angle = max(-45, min(45, normalized_angle))
        
        # Tính toán độ lệch tâm ngang (pixel)
        error_x = int(x_center - FRAME_CENTER_X)
        
        return True, error_x, int(normalized_angle), largest_contour, min_rect
    
    def control_robot(self, detected: bool, error_x: int, angle: int) -> tuple:
        """
        Điều khiển Hybrid: Kết hợp Error_X và Angle thành một sai số tổng hợp
        sau đó đưa qua bộ PID để tính toán góc bẻ lái mịn.
        """
        if not detected:
            # Không thấy vạch: Xoay tại chỗ để tìm kiếm
            set_motors_direction('rotate_left', MOTOR_SPEED, 0, 0)
            return "Searching (Rotate Left)", 0.0

        # CÔNG THỨC HYBRID: Kết hợp vị trí tâm và hướng nghiêng của vạch
        # Ví dụ: Xe đang lệch phải (error_x > 0) và vạch lại quẹo phải (angle > 0) 
        # -> Sai số tổng hợp sẽ lớn hơn, bộ PID sẽ ra lệnh bẻ lái mạnh mẽ hơn để ôm cua.
        hybrid_error = error_x + (angle * ANGLE_WEIGHT)
        
        # Tính toán tín hiệu đầu ra từ bộ PID
        pid_output = self.pid.calculate(error=hybrid_error)
        
        # Giới hạn góc lái (Steering Clamp)
        pid_output = max(-PID_MAX_OUTPUT, min(PID_MAX_OUTPUT, pid_output))
        
        # Gửi lệnh điều khiển tuyến tính mượt mà cho robot tiến lên kèm góc lái theta
        set_motors_direction('go_forward', MOTOR_SPEED, 0, pid_output)
        
        return "Line Following (PID)", pid_output

    def visualize(self, frame: np.ndarray, detected: bool, error_x: int, 
                  angle: int, contour: np.ndarray, min_rect: tuple, status: str, pid_out: float) -> None:
        """Vẽ dữ liệu trực quan sinh động hỗ trợ debug."""
        # Vẽ vạch chữ thập trung tâm màn hình
        cv2.line(frame, (FRAME_CENTER_X, 0), (FRAME_CENTER_X, FRAME_HEIGHT), (0, 255, 0), 1)
        
        if detected and min_rect is not None:
            # Vẽ hộp xoay bao quanh vạch đỏ
            box = cv2.boxPoints(min_rect)
            box = np.intp(box)
            cv2.drawContours(frame, [box], 0, (0, 0, 255), 2)
            
            # Vẽ tâm vật thể
            cx, cy = int(min_rect[0][0]), int(min_rect[0][1])
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)
            
            # Hiển thị thông số dạng số
            cv2.putText(frame, f"Error X: {error_x}px | Angle: {angle}deg", (10, 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"PID Output (Steer): {pid_out:.3f}", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        else:
            cv2.putText(frame, "STATUS: NO LINE", (10, 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        
        cv2.putText(frame, f"Mode: {status}", (10, FRAME_HEIGHT - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    def run(self) -> None:
        """Vòng lặp chính xử lý Real-time."""
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Lỗi: Không thể đọc frame từ camera")
                    break
                
                # 1. Xử lý ảnh lọc vạch đỏ
                mask = self.process_frame(frame)
                
                # 2. Phân tích hình học nâng cao (Lấy cả Error X lẫn Góc Angle)
                detected, err_x, angle, contour, min_rect = self.analyze_line_geometry(mask)
                
                # 3. Tính toán PID Lai và điều khiển motor
                status, pid_out = self.control_robot(detected, err_x, angle)
                
                # 4. Hiển thị thông tin đồ họa
                self.visualize(frame, detected, err_x, angle, contour, min_rect, status, pid_out)
                cv2.imshow("Red Line Tracking (PID + RotatedRect)", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            self.cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        tracker = RedLineTracker()
        tracker.run()
    except RuntimeError as e:
        print(f"\n[LỖI HỆ THỐNG]: {e}")
    except KeyboardInterrupt:
        print("\n[THÔNG BÁO]: Đã dừng chương trình bằng tổ hợp phím (Ctrl+C).")
    except Exception as e:
        print(f"\n[LỖI KHÔNG XÁC ĐỊNH]: {e}")