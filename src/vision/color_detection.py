"""
Color Detection Module
Detects and tracks colored objects (red, yellow, blue) in video streams.
Provides frame data with detection results to a queue for processing.
"""

import cv2
import time
from typing import Callable, Any, Optional, Tuple
from threading import Event
from queue import Queue

from src.utils.image_utils import (
    process_frame,
    analyze_contours,
    display_info,
    calculate_fps
)
from src.utils.logger import Logger

# ============= Color Detection Configuration =============
DEFAULT_MAX_FPS = 10
FRAME_QUEUE_SIZE = 30

logger = Logger()


def color_detection_loop(videostream: Any, center_x: int, center_y: int, 
                        min_box_area: int, stop_event: Event, frame_queue: Queue, 
                        max_fps: int = DEFAULT_MAX_FPS) -> None:
    """
    Main color detection loop that processes video frames and detects colors.
    
    Detects red, yellow, and blue colored objects in the video stream.
    Results are put into a queue for consumption by other components.
    
    Args:
        videostream: Video stream object with read() method
        center_x: X coordinate of frame center for deviation calculation
        center_y: Y coordinate of frame center for deviation calculation
        min_box_area: Minimum contour area to consider as valid detection
        stop_event: Threading event to signal loop termination
        frame_queue: Queue to put detection results into
        max_fps: Target maximum FPS for processing (default 10)
    """
    logger.log_info(f"Starting color detection loop with max {max_fps} FPS")
    
    frame_rate = 1
    freq = cv2.getTickFrequency()
    frame_interval = 1.0 / max_fps
    last_time = time.time()
    
    try:
        while not stop_event.is_set():
            current_time = time.time()
            
            # FPS throttling
            if current_time - last_time < frame_interval:
                continue
            
            # Read frame from video stream
            frame = videostream.read()
            if frame is None:
                logger.log_warning("Cannot read frame from video stream")
                break
            
            t1 = cv2.getTickCount()
            
            # Process frame to extract color masks
            mask_red, mask_yellow, mask_blue = process_frame(frame)
            
            # Analyze contours for each color
            (status_red, x_r, y_r, contours_red, 
             x_red, y_red, w_red, h_red) = analyze_contours(
                mask_red, center_x, center_y, min_box_area, "red")
            
            (status_yellow, x_y, y_y, contours_yellow, 
             x_yellow, y_yellow, w_yellow, h_yellow) = analyze_contours(
                mask_yellow, center_x, center_y, min_box_area, "yellow")
            
            (status_blue, x_b, y_b, contours_blue, 
             x_blue, y_blue, w_blue, h_blue) = analyze_contours(
                mask_blue, center_x, center_y, min_box_area, "blue")
            
            # Calculate deviations from center
            deviation_x_red = (x_red + w_red // 2) - center_x if status_red else 0
            deviation_y_red = (y_red + h_red // 2) - center_y if status_red else 0
            deviation_x_yellow = (x_yellow + w_yellow // 2) - center_x if status_yellow else 0
            deviation_y_yellow = (y_yellow + h_yellow // 2) - center_y if status_yellow else 0
            deviation_x_blue = (x_blue + w_blue // 2) - center_x if status_blue else 0
            deviation_y_blue = (y_blue + h_blue // 2) - center_y if status_blue else 0
            
            # Prepare frame data tuple
            frame_data = (
                frame, mask_red, mask_yellow, mask_blue,
                status_red, deviation_x_red, deviation_y_red,
                status_yellow, deviation_x_yellow, deviation_y_yellow,
                status_blue, deviation_x_blue, deviation_y_blue,
                contours_red, contours_yellow, contours_blue,
                x_red, y_red, w_red, h_red,
                x_yellow, y_yellow, w_yellow, h_yellow,
                x_blue, y_blue, w_blue, h_blue
            )
            
            # Put results in queue if not full
            if not frame_queue.full():
                try:
                    frame_queue.put(frame_data)
                except Exception as e:
                    logger.log_warning(f"Error putting frame data in queue: {e}")
            
            # Display detection info
            display_info(frame, f'FPS: {frame_rate:.1f}', 
                        [str(status_red), str(status_yellow), str(status_blue)],
                        [(x_r, y_r), (x_y, y_y), (x_b, y_b)], 
                        center_x, center_y)
            
            # Calculate FPS
            t2 = cv2.getTickCount()
            frame_rate = calculate_fps(t1, t2, freq)
            last_time = current_time
    
    except Exception as e:
        logger.log_error(f"Error in color detection loop: {e}")
    
    finally:
        logger.log_info("Color detection loop stopped")