# System Architecture

Professional-grade robot control system following industrial standards.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Main Application                       │
│  (main.py, server.py, line_tracker.py)                  │
└──────────────┬────────────────────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │     State Machine + Watchdog         │
        │  (core/state_machine.py)            │
        │  (core/watchdog.py)                 │
        │  (core/safe_stop.py)                │
        └──────┬──────────────────────────────┘
               │
    ┌──────────┼──────────────┐
    │          │              │
    ▼          ▼              ▼
┌────────┐ ┌────────┐  ┌─────────────┐
│Control │ │ Vision │  │  Hardware   │
│ PID    │ │ Color  │  │  Motors     │
│ Obstacle│ │ Detect │  │  Sensors    │
└────────┘ └────────┘  └─────────────┘
    │          │              │
    └──────────┼──────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │      Configuration Manager           │
        │  (core/config_manager.py)           │
        │  YAML: robot_config.yaml            │
        └──────────────────────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │      Utilities & Logging             │
        │  (utils/lifecycle_logger.py)        │
        │  (utils/rate_limiter.py)            │
        │  (utils/circular_buffer.py)         │
        └──────────────────────────────────────┘
```

---

## 📦 Module Responsibilities

### Core Modules (`src/core/`)

#### state_machine.py
- **Purpose**: Robot operational state management
- **States**: INIT, IDLE, MANUAL, AUTO_MISSION, WATERING, SEARCHING, OBSTACLE_AVOID, RETURN_TO_CHARGER, CHARGING, ERROR, EMERGENCY_STOP
- **Features**:
  - Valid transition validation
  - State entry callbacks
  - Timeout management
  - Logging integration

#### watchdog.py
- **Purpose**: System health monitoring
- **Features**:
  - Periodic heartbeat checking
  - Status levels: NORMAL, WARNING, CRITICAL, EMERGENCY_STOP
  - Emergency stop triggering
  - Motor shutdown on timeout
- **Usage**: Call `watchdog.heartbeat()` in main loop

#### safe_stop.py
- **Purpose**: Graceful shutdown and emergency handling
- **Features**:
  - Registered shutdown handlers
  - Emergency handlers
  - Cleanup coordination
  - Shutdown state tracking

#### config_manager.py
- **Purpose**: Centralized configuration from YAML
- **Features**:
  - Schema validation (Pydantic)
  - YAML parsing and flattening
  - Configuration sections: Hardware, Vision, Control, Safety
  - Config save/load

---

### Control Modules (`src/control/`)

#### pid_controller.py
- **Purpose**: PID control for line tracking
- **Features**:
  - Proportional, Integral, Derivative terms
  - Anti-windup integral limiting
  - Output limiting
  - Statistics tracking
  - Dynamic gain adjustment

#### obstacle_avoider.py (Future)
- Wall-following algorithm
- Random rotation fallback
- Sensor-based decision making

#### mission_planner.py (Future)
- Mission sequencing
- Goal coordination
- Path planning

---

### Vision Modules (`src/vision/`)

#### color_detection.py
- Red/yellow/blue color detection
- HSV-based masking
- Contour analysis
- Frame queue publishing

#### object_detection.py
- TensorFlow Lite model inference
- Plant detection
- Confidence filtering

---

### Hardware Modules (`src/hardware/`)

#### motors.py
- Motor speed control
- PWM management
- Stop functionality

#### battery.py
- INA219 voltage/current reading
- Battery percentage calculation
- Remaining time estimation

#### ultrasonic.py
- Distance sensor reading
- Obstacle detection
- Multi-sensor coordination

#### relay.py
- Water pump control
- On/off relay management

#### servos.py
- Camera servo angles
- Pan/tilt control

---

### Utility Modules (`src/utils/`)

#### lifecycle_logger.py
- Event logging
- Error logging
- Trace/debug logging
- Performance metrics
- Session management

#### rate_limiter.py
- Loop frequency control
- Actual frequency measurement
- Period enforcement

#### circular_buffer.py
- Fixed-size sensor data storage
- Average calculation
- Numpy integration

---

## 🔄 Execution Flow

### Main Loop (20 Hz)

```python
while True:
    # 1. Watchdog heartbeat
    watchdog.heartbeat()
    
    # 2. Read sensors
    sensor_data = read_sensors()
    
    # 3. Check safety
    if sensor_data.emergency:
        state_machine.transition_to(RobotState.EMERGENCY_STOP)
    
    # 4. Process current state
    match state_machine.current_state:
        case RobotState.AUTO_MISSION:
            execute_mission(sensor_data)
        case RobotState.WATERING:
            watering_task(sensor_data)
        # ... other states
    
    # 5. Rate limit
    rate_limiter.sleep()
```

---

## 🔐 Safety Mechanisms

### Watchdog System
```
Main Loop
    ├─ Calls watchdog.heartbeat()
    │
    └─> Monitor Thread (every 0.1s)
        ├─ Check last heartbeat time
        ├─ If > timeout: set status CRITICAL
        ├─ If > timeout*2: trigger EMERGENCY_STOP
        └─ Call emergency callbacks
```

### Safe Stop System
```
Graceful Shutdown:
    1. Signal shutdown start
    2. Execute registered handlers in order
    3. Wait for cleanup
    4. Log completion

Emergency Stop:
    1. Set stopping flag immediately
    2. Execute emergency handlers (async)
    3. Stop all motors (hardware level)
    4. Log critical event
```

---

## 📊 Configuration Hierarchy

```
robot_config.yaml
    ├── hardware
    │   ├── motors
    │   ├── ultrasonic
    │   └── camera
    ├── vision
    │   ├── red_line
    │   └── object_detection
    ├── control
    │   ├── pid
    │   └── obstacle_avoidance
    └── safety
        ├── watchdog_timeout
        ├── battery_thresholds
        └── motor_limits
```

**Access in Code**:
```python
config_mgr = ConfigManager()
hw_config = config_mgr.get_hardware()
motor_speed = hw_config.motors_max_speed
```

---

## 🧵 Threading Model

### Main Thread
- Primary control loop (20 Hz)
- State machine processing
- Sensor reading
- Motor control

### Watchdog Thread (Daemon)
- Background monitoring
- Heartbeat checking
- Emergency detection

### Vision Thread (Optional)
- Camera frame capture
- Color detection processing
- Object detection inference

### Web Server Thread (Flask)
- HTTP request handling
- Remote control
- Status reporting

---

## 📝 Logging Architecture

### Three-Level Logging

```
System Events (events.log)
    └─ State transitions, mission events, high-level info

Error Logging (errors.log)
    └─ Hardware faults, exceptions, critical issues

Trace Logging (trace.log)
    └─ Sensor readings, debug info, performance metrics
```

**Usage**:
```python
from src.utils.lifecycle_logger import LifecycleLogger

logger = LifecycleLogger()
logger.log_state_transition("IDLE", "AUTO_MISSION", "User command")
logger.log_hardware_fault("camera", "Connection timeout", "CRITICAL")
logger.log_periodic_snapshot(system_state_dict)
```

---

## 🔗 Integration Points

### Adding New Hardware Module
1. Create class in `src/hardware/`
2. Implement initialization and control methods
3. Add configuration to `config_manager.py`
4. Update YAML config
5. Integrate in state machine

### Adding New Control Algorithm
1. Create module in `src/control/`
2. Implement control logic
3. Add PID parameters to config if needed
4. Call from appropriate state in state machine
5. Log performance metrics

### Adding New Vision Feature
1. Create module in `src/vision/`
2. Implement detection/processing
3. Put results in frame queue
4. Add configuration options
5. Integrate with mission controller

---

## 📈 Performance Considerations

### Main Loop Frequency: 20 Hz
- Motor updates: 20 Hz
- Sensor polling: 20 Hz
- State machine: 20 Hz

### Vision Processing: 10 Hz (Optional)
- Run in separate thread
- Frame skipping for performance
- Configurable via `frame_skip` parameter

### Watchdog Check: 100 Hz
- Fast response to heartbeat loss
- Minimal overhead

---

## 🚀 Extension Points

### Future Modules
- `src/control/obstacle_avoider.py` - Wall following
- `src/control/mission_planner.py` - Complex missions
- `src/hardware/drivers/` - Device-specific drivers
- `src/hardware/health_monitor.py` - Hardware diagnostics
- `src/hardware/fault_injection.py` - Testing support

### Cloud Integration (MQTT)
```python
mqtt_client.publish("robot/status", robot_status_json)
mqtt_client.subscribe("robot/command/+")
```

---

## 🏆 Design Principles

1. **Modularity** - Independent, reusable components
2. **Safety** - Multiple layers of protection
3. **Observability** - Comprehensive logging
4. **Configurability** - YAML-based settings
5. **Testability** - Clear interfaces
6. **Performance** - Efficient algorithms
7. **Reliability** - Error recovery
8. **Maintainability** - Clean code standards

---

## 📚 See Also

- [README.md](README.md) - Usage guide
- [config/robot_config.yaml](config/robot_config.yaml) - Configuration reference
- [OPTIMIZATION_REPORT.md](OPTIMIZATION_REPORT.md) - Code quality improvements
