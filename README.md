# Automated Plant-Watering Robot 🤖

Professional-grade automated plant watering system with computer vision, obstacle avoidance, and remote monitoring.

## 🎯 Features

### Core Capabilities
- ✅ **Autonomous Navigation** - Line tracking and obstacle avoidance
- ✅ **Computer Vision** - Red line detection and plant identification
- ✅ **Precision Watering** - Automated plant detection and targeted watering
- ✅ **Battery Management** - INA219 voltage/current monitoring
- ✅ **Manual Control** - Web interface and keyboard control
- ✅ **Safety Systems** - Watchdog monitoring and emergency stop

### System Architecture
- ✅ **State Machine** - Professional robot state management
- ✅ **PID Control** - Line tracking with tunable PID controller
- ✅ **Configuration Management** - Centralized YAML configuration
- ✅ **Lifecycle Logging** - Comprehensive event and error logging
- ✅ **Rate Limiting** - Frequency-controlled main loops
- ✅ **Circular Buffers** - Efficient sensor data storage

---

## 📁 Project Structure

```
Automated-plant-watering-robot/
│
├── config/                          # Configuration files
│   └── robot_config.yaml           # Central configuration (YAML)
│
├── models/                          # AI/ML Models
│   ├── detect.tflite               # TensorFlow Lite detection model
│   ├── labelmap.txt
│   └── pipeline_file.config
│
├── src/                             # Main source code
│
│   ├── core/                        # Core system modules
│   │   ├── __init__.py
│   │   ├── state_machine.py        # Robot state management
│   │   ├── watchdog.py             # System health monitoring
│   │   ├── safe_stop.py            # Emergency stop mechanism
│   │   └── config_manager.py       # Configuration management
│   │
│   ├── control/                     # Control modules
│   │   ├── __init__.py
│   │   ├── pid_controller.py       # PID for line tracking
│   │   ├── obstacle_avoider.py     # Obstacle avoidance
│   │   └── mission_planner.py      # Mission planning
│   │
│   ├── hardware/                    # Hardware control
│   │   ├── battery.py              # Battery monitoring
│   │   ├── kinematic.py            # Robot kinematics
│   │   ├── motors.py               # Motor control
│   │   ├── relay.py                # Relay (pump) control
│   │   ├── servos.py               # Servo control
│   │   ├── time_manager.py
│   │   ├── ultrasonic.py           # Ultrasonic sensors
│   │   └── water_sensor.py
│   │
│   ├── utils/                       # Utility modules
│   │   ├── logger.py               # Standard logging
│   │   ├── lifecycle_logger.py     # Detailed lifecycle logging
│   │   ├── rate_limiter.py         # Loop frequency control
│   │   ├── circular_buffer.py      # Efficient data storage
│   │   ├── control_utils.py
│   │   └── image_utils.py
│   │
│   ├── vision/                      # Computer vision
│   │   ├── color_detection.py      # Color-based detection
│   │   ├── object_detection.py     # TensorFlow Lite detection
│   │   └── video_stream.py
│   │
│   └── robot/
│       └── modes.py                 # Robot operation modes
│
├── templates/                       # Web interface HTML
│   └── index.html
│
├── extensions/                      # Extension modules (future)
│   └── __init__.py
│
├── raw/                             # Raw sensor data storage
│
├── main.py                          # Main entry point
├── server.py                        # Flask web server
├── line_tracker.py                  # Line tracking module
├── test_features.py                 # Feature testing
│
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── OPTIMIZATION_REPORT.md           # Code optimization report
├── robot.log                        # System log file
└── README.md                        # This file

```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Raspberry Pi 4 or Jetson Nano
- GPIO-compatible development board
- USB camera
- TensorFlow Lite runtime

### Installation

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd Automated-plant-watering-robot/Automation
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure system**
   Edit `config/robot_config.yaml` with your specific settings:
   - Motor GPIO pins
   - Camera resolution and FPS
   - PID controller gains
   - Safety thresholds

### Running the Robot

**Manual Mode** (keyboard control)
```bash
python main.py
# Choose option 1 from menu
```

**Automatic Mode** (autonomous watering)
```bash
python main.py
# Choose option 2 from menu
```

**Web Interface**
```bash
python server.py
# Navigate to http://<robot-ip>:5000
```

**Test Features**
```bash
python test_features.py
```

---

## 📋 Configuration Guide

All settings are in `config/robot_config.yaml`:

### Hardware Configuration
```yaml
hardware:
  motors:
    max_speed: 1.0              # 0-1 (normalized)
    acceleration_time: 0.5      # seconds
    pwm_frequency: 1000         # Hz
  
  ultrasonic:
    safe_distance_cm: 30        # Minimum safe distance
    critical_distance_cm: 15    # Emergency stop distance
```

### Vision Configuration
```yaml
vision:
  red_line:
    min_contour_area: 500       # Minimum detection size
  object_detection:
    confidence_threshold: 0.7   # Detection certainty
    frame_skip: 2               # Process every Nth frame
```

### Control Configuration
```yaml
control:
  pid:
    kp: 0.5    # Proportional gain (increase for faster response)
    ki: 0.01   # Integral gain (prevents steady-state error)
    kd: 0.1    # Derivative gain (dampens oscillation)
```

### Safety Configuration
```yaml
safety:
  watchdog_timeout: 0.5         # Emergency stop timeout
  battery_min_voltage: 14.8     # Safe minimum voltage
  battery_critical_voltage: 14.0 # Critical threshold
```

---

## 🎮 Operation Modes

### Manual Mode
- **W/A/S/D** - Movement control
- **Q/E/Z/X** - Diagonal movement
- **1/2/3** - Special commands
- **+/-** - Speed adjustment
- **R** - Activate water pump

### Automatic Mode
- Robot autonomously:
  1. Searches for plants using object detection
  2. Tracks red line path
  3. Avoids obstacles
  4. Waters detected plants
  5. Returns to charging station

### Charging Mode
- Detects charging station via red line
- Docks automatically
- Charges battery until threshold

---

## 🧠 State Machine

```
[INIT] → [IDLE] ← → [MANUAL] (keyboard control)
          ↓ ↓
      [AUTO_MISSION]
        ↓ ↓ ↓ ↓
    [WATERING] [SEARCHING] [OBSTACLE_AVOID] [RETURN_TO_CHARGER]
        ↓         ↓            ↓                 ↓
    [CHARGING]  ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
    
    Any state → [ERROR] → [RECOVERY] or [IDLE]
    Any state → [EMERGENCY_STOP] (watchdog timeout)
```

---

## 📊 PID Tuning Guide

### For Line Tracking
1. **Start with zeros**: kp=0, ki=0, kd=0
2. **Set Kp** (P-term): Increase until oscillation occurs
3. **Reduce Kp** by 50% for stability
4. **Add Ki** slowly to remove steady-state error
5. **Add Kd** to dampen oscillation

### Example Values
- Fast tracking: kp=0.8, ki=0.05, kd=0.2
- Smooth tracking: kp=0.3, ki=0.01, kd=0.05
- Conservative: kp=0.2, ki=0.005, kd=0.02

---

## 🔍 Logging & Debugging

### Log Levels
- **Events** (`robot_events.log`) - State changes, missions
- **Errors** (`robot_errors.log`) - Hardware faults, exceptions
- **Trace** (`robot_trace.log`) - Sensor readings, detailed debug

### Example Log Analysis
```bash
# View events
tail -f logs/*_events.log

# Find errors
grep "ERROR\|CRITICAL" logs/*_errors.log

# Monitor in real-time
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
```

---

## 🛡️ Safety Systems

### Watchdog Timer
- Monitors main loop heartbeat
- Triggers emergency stop if timeout
- Automatic motor shutdown

### Safe Stop Mechanism
- Graceful shutdown with cleanup
- Emergency stop with immediate halt
- Registered handlers for cleanup

### Battery Management
- Voltage monitoring (INA219)
- Critical voltage alerts
- Automatic return-to-charger

---

## 📈 Performance Specifications

| Metric | Value |
|--------|-------|
| Max Speed | 0.5 m/s |
| Max Acceleration | 0.2 m/s² |
| Line Tracking Accuracy | ±5cm |
| Obstacle Detection Range | 10-100cm |
| Battery Runtime | 2-4 hours |
| Charge Time | 2 hours |
| Main Loop Frequency | 20 Hz |
| Vision Processing | 10 FPS |

---

## 🔧 Development

### Code Quality
- **Type Hints**: Full coverage (mypy compatible)
- **Docstrings**: Google-style for all functions
- **PEP 8**: Black formatting
- **Testing**: pytest + coverage

### Development Setup
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest --cov=src tests/

# Format code
black src/

# Type check
mypy src/

# Lint
pylint src/
```

### Adding New Modules
1. Create module in appropriate `src/` subdirectory
2. Add type hints and docstrings
3. Update configuration if needed
4. Add unit tests
5. Update imports and documentation

---

## 🐛 Troubleshooting

### Robot doesn't move
- Check GPIO configuration matches hardware
- Verify motor power supply
- Test motor speeds: `python -c "from src.hardware.motors import Motors; Motors().set_speed('motor_1', 0.5)"`

### Camera feed unavailable
- Check USB camera connection
- Verify `/dev/video0` exists
- Test with: `v4l2-ctl --list-devices`

### Line not detected
- Verify red line brightness and contrast
- Adjust HSV thresholds in `config/robot_config.yaml`
- Check lighting conditions
- Run: `python test_features.py`

### Battery not charging
- Check charging station red line
- Verify relay GPIO pin configuration
- Test relay: `python -c "from src.hardware.relay import RelayControl; RelayControl(5).on()"`

---

## 📡 Remote Monitoring (Future)

MQTT support for cloud monitoring:
```python
# Will connect to MQTT broker and publish telemetry
mqtt_client.publish("robot/status", json.dumps(telemetry))
```

---

## 📄 License

[MIT License](LICENSE)

---

## 👥 Contributors

- Development Team
- Computer Vision: OpenCV, TensorFlow Lite
- Hardware: gpiozero, smbus2

---

## 📚 Resources

- [gpiozero Documentation](https://gpiozero.readthedocs.io/)
- [OpenCV Tutorials](https://docs.opencv.org/)
- [TensorFlow Lite Guide](https://www.tensorflow.org/lite/guide)
- [PID Control Tutorial](https://en.wikipedia.org/wiki/Proportional%E2%80%93integral%E2%80%93derivative_controller)

---

## 🤝 Support

For issues and questions:
1. Check troubleshooting section above
2. Review log files in `logs/` directory
3. Consult configuration guide
4. Check existing issues/documentation

**Last Updated**: May 25, 2026  
**Version**: 2.0 (Professional Architecture)
