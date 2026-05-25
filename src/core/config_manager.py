"""
Configuration Manager Module
Centralized configuration management with YAML support.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)


class HardwareConfig(BaseModel):
    """Hardware configuration schema."""
    motors_max_speed: float = 1.0
    motors_acceleration_time: float = 0.5
    motors_pwm_frequency: int = 1000
    ultrasonic_safe_distance: int = 30
    ultrasonic_critical_distance: int = 15
    ultrasonic_sample_rate: int = 20
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    camera_auto_reconnect: bool = True


class VisionConfig(BaseModel):
    """Vision configuration schema."""
    red_line_min_area: int = 500
    object_detection_confidence: float = 0.7
    object_detection_frame_skip: int = 2


class ControlConfig(BaseModel):
    """Control configuration schema."""
    pid_kp: float = 0.5
    pid_ki: float = 0.01
    pid_kd: float = 0.1
    pid_output_max: float = 1.0
    pid_output_min: float = -1.0
    obstacle_avoidance_strategy: str = "wall_following"


class SafetyConfig(BaseModel):
    """Safety configuration schema."""
    watchdog_timeout: float = 0.5
    battery_min_voltage: float = 14.8
    battery_critical_voltage: float = 14.0
    max_motor_current: float = 2.5


class RobotConfig(BaseModel):
    """Complete robot configuration."""
    hardware: HardwareConfig = HardwareConfig()
    vision: VisionConfig = VisionConfig()
    control: ControlConfig = ControlConfig()
    safety: SafetyConfig = SafetyConfig()


class ConfigManager:
    """
    Manage robot configuration from YAML files.
    """
    
    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config YAML file
        """
        self.config_path = Path(config_path or "config/robot_config.yaml")
        self.config: RobotConfig = RobotConfig()
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            logger.info("Using default configuration")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Parse with validation
            config_dict = self._flatten_yaml(data)
            self.config = RobotConfig(**config_dict)
            
            logger.info(f"Configuration loaded from {self.config_path}")
        
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            logger.info("Using default configuration")
        
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
    
    def _flatten_yaml(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten nested YAML structure to flat config dictionary.
        
        Args:
            data: Nested YAML data
        
        Returns:
            Flattened configuration dictionary
        """
        flat = {}
        
        # Hardware section
        if 'hardware' in data:
            hw = data['hardware']
            if 'motors' in hw:
                flat['motors_max_speed'] = hw['motors'].get('max_speed', 1.0)
                flat['motors_acceleration_time'] = hw['motors'].get('acceleration_time', 0.5)
                flat['motors_pwm_frequency'] = hw['motors'].get('pwm_frequency', 1000)
            
            if 'ultrasonic' in hw:
                flat['ultrasonic_safe_distance'] = hw['ultrasonic'].get('safe_distance_cm', 30)
                flat['ultrasonic_critical_distance'] = hw['ultrasonic'].get('critical_distance_cm', 15)
                flat['ultrasonic_sample_rate'] = hw['ultrasonic'].get('sample_rate_hz', 20)
            
            if 'camera' in hw:
                flat['camera_width'] = hw['camera'].get('width', 640)
                flat['camera_height'] = hw['camera'].get('height', 480)
                flat['camera_fps'] = hw['camera'].get('fps', 30)
                flat['camera_auto_reconnect'] = hw['camera'].get('auto_reconnect', True)
        
        # Vision section
        if 'vision' in data:
            vision = data['vision']
            if 'object_detection' in vision:
                flat['object_detection_confidence'] = vision['object_detection'].get('confidence_threshold', 0.7)
                flat['object_detection_frame_skip'] = vision['object_detection'].get('frame_skip', 2)
            if 'red_line' in vision:
                flat['red_line_min_area'] = vision['red_line'].get('min_contour_area', 500)
        
        # Control section
        if 'control' in data:
            ctrl = data['control']
            if 'pid' in ctrl:
                flat['pid_kp'] = ctrl['pid'].get('kp', 0.5)
                flat['pid_ki'] = ctrl['pid'].get('ki', 0.01)
                flat['pid_kd'] = ctrl['pid'].get('kd', 0.1)
                limits = ctrl['pid'].get('output_limits', [-1.0, 1.0])
                flat['pid_output_min'] = limits[0]
                flat['pid_output_max'] = limits[1]
            if 'obstacle_avoidance' in ctrl:
                flat['obstacle_avoidance_strategy'] = ctrl['obstacle_avoidance'].get('strategy', 'wall_following')
        
        # Safety section
        if 'safety' in data:
            safety = data['safety']
            flat['watchdog_timeout'] = safety.get('watchdog_timeout', 0.5)
            flat['battery_min_voltage'] = safety.get('battery_min_voltage', 14.8)
            flat['battery_critical_voltage'] = safety.get('battery_critical_voltage', 14.0)
            flat['max_motor_current'] = safety.get('max_motor_current', 2.5)
        
        return flat
    
    def get_hardware(self) -> HardwareConfig:
        """Get hardware configuration."""
        return self.config.hardware
    
    def get_vision(self) -> VisionConfig:
        """Get vision configuration."""
        return self.config.vision
    
    def get_control(self) -> ControlConfig:
        """Get control configuration."""
        return self.config.control
    
    def get_safety(self) -> SafetyConfig:
        """Get safety configuration."""
        return self.config.safety
    
    def save_config(self, path: Optional[str] = None) -> None:
        """
        Save current configuration to YAML file.
        
        Args:
            path: Save path (default: original path)
        """
        save_path = Path(path or self.config_path)
        
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config.dict(), f, default_flow_style=False)
            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
