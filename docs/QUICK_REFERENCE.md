# Quick Reference: Advanced Control API 🚀

## LineFollower API

```python
from src.control import LineFollower, LineFollowingStrategy

# Initialize
follower = LineFollower(
    frame_width=640,
    frame_height=480,
    strategy=LineFollowingStrategy.BALANCED  # AGGRESSIVE | BALANCED | CONSERVATIVE
)

# Detect line
detection = follower.detect_line(frame)
# Returns: LineDetectionResult
#   .detected (bool)
#   .center_x, .center_y (float)
#   .quality_score (0-100)
#   .angle (degrees)
#   .area, .width (float)

# Get control output
control = follower.calculate_control(detection, forward_speed=0.5)
# Returns: ControlOutput
#   .velocity_forward (-1.0 to 1.0)
#   .angular_velocity (-1.0 to 1.0)
#   .confidence (0-1.0)

# Change strategy
follower.set_strategy(LineFollowingStrategy.AGGRESSIVE)
follower.adapt_strategy(recent_quality_score)  # Auto-select

# Get metrics
metrics = follower.get_performance_metrics()
# Keys: detection_rate, cte_avg, cte_std, cte_max

# Tuning
follower.pid_cross_track.set_gains(kp=0.8, ki=0.15, kd=0.4)
follower.quality_threshold = 30.0
follower.min_contour_area = 500
```

---

## ObstacleAvoider API

```python
from src.control import (
    ObstacleAvoider, AvoidanceStrategy, AvoidanceCommand, ObstacleData
)

# Initialize
avoider = ObstacleAvoider(
    strategy=AvoidanceStrategy.WALL_FOLLOWING,  # POTENTIAL_FIELD | RANDOM_WALK | BUG_ALGORITHM | HYBRID
    critical_distance=0.3,  # Stop distance (meters)
    safe_distance=0.5       # Preferred distance
)

# Update sensors
sensor_data = ObstacleData(
    front_distance=0.6,
    left_distance=0.4,
    right_distance=1.2,
    rear_distance=2.0,
    timestamp=time.time()
)

# Get avoidance command
command = avoider.calculate_avoidance(sensor_data)
# Returns: AvoidanceCommand
#   .linear_velocity (-1.0 to 1.0)
#   .angular_velocity (-1.0 to 1.0)
#   .strategy_used (AvoidanceStrategy)
#   .obstacle_detected (bool)
#   .confidence (0-1.0)

# Change strategy
avoider.set_strategy(AvoidanceStrategy.POTENTIAL_FIELD)

# Tuning
avoider.wall_distance_target = 0.6  # Wall follow distance
avoider.wall_follow_side = "right"  # "left" or "right"
avoider.critical_distance = 0.25

# Get metrics
metrics = avoider.get_performance_metrics()
# Keys: collision_count, avoidance_maneuvers, strategy_changes
```

---

## MotorController API

```python
from src.control import MotorController, MotorControlMode, RobotKinematics

# Initialize
motors = MotorController(
    num_motors=4,
    mode=MotorControlMode.VELOCITY,  # DIRECT | VELOCITY | TORQUE
    kinematics=RobotKinematics(
        wheel_radius=0.05,
        wheel_separation=0.15,
        max_linear_velocity=0.5,
        max_angular_velocity=2.0
    )
)

# Set velocity command (kinematics-based)
motors.set_velocity_command(
    linear_velocity=0.5,   # -1.0 to 1.0
    angular_velocity=0.2   # -1.0 to 1.0
)

# Direct motor control
motors.set_target_speed(
    motor_indices=[0, 1, 2, 3],
    speeds=[0.5, 0.5, 0.5, 0.5],
    accelerations=[0.5, 0.5, 0.5, 0.5]  # Ramp rate (0-2)
)

# Update (apply smooth ramping)
pwm_values = motors.update()
# Returns: numpy array of smoothly-ramped speeds

# Stop motors
motors.stop_motor(motor_index=0, deceleration=1.0)  # Single motor
motors.stop_all_motors(deceleration=1.0)            # All motors
motors.emergency_stop()                              # Immediate stop

# Get motor status
status = motors.get_motor_status(motor_index=0)
# Keys: current_speed, target_speed, acceleration, current_amps

# Get overall metrics
metrics = motors.get_performance_metrics()
# Keys: average_speed, max_speed, average_current, current_limit_events

# Configuration
motors.accelerations = [0.5, 0.5, 0.5, 0.5]  # Ramp rates
motors.max_currents = [2.0, 2.0, 2.0, 2.0]   # Current limits (A)
motors.mode = MotorControlMode.VELOCITY
```

---

## Integration Pattern

```python
# Core loop
while True:
    # Vision
    frame = camera.read()
    detection = line_follower.detect_line(frame)
    
    # Sensors
    sensor_data = read_ultrasonic()
    
    # Decision
    if detection.detected and detection.quality_score > 50:
        control = line_follower.calculate_control(detection)
        if sensor_data.front_distance > 0.6:
            motors.set_velocity_command(control.velocity_forward, control.angular_velocity)
        else:
            avoidance = obstacle_avoider.calculate_avoidance(sensor_data)
            motors.set_velocity_command(avoidance.linear_velocity, avoidance.angular_velocity)
    else:
        avoidance = obstacle_avoider.calculate_avoidance(sensor_data)
        motors.set_velocity_command(avoidance.linear_velocity, avoidance.angular_velocity)
    
    # Apply
    pwm = motors.update()
    apply_to_motors(pwm)
    
    # Monitor (every 100 iterations)
    if iteration % 100 == 0:
        line_metrics = line_follower.get_performance_metrics()
        obstacle_metrics = obstacle_avoider.get_performance_metrics()
        motor_metrics = motors.get_performance_metrics()
        print(f"Detection: {line_metrics['detection_rate']:.1f}%")
```

---

## Strategy Selection Quick Guide

| Task | Recommended Strategy | Alternative |
|------|----------------------|-------------|
| **Good line quality** | AGGRESSIVE (Kp=1.5) | BALANCED |
| **Poor/variable quality** | CONSERVATIVE (Kp=0.4) | BALANCED |
| **Unknown line quality** | BALANCED (Kp=0.8) | - |
| **Corridor navigation** | WALL_FOLLOWING | HYBRID |
| **Open area navigation** | POTENTIAL_FIELD | HYBRID |
| **Emergency/stuck** | RANDOM_WALK | WALL_FOLLOWING |
| **Dynamic environment** | HYBRID | - |

---

## Performance Targets

```
Detection Rate:        > 90%
CTE (Cross-Track):     < 15 pixels
CTE Std Dev:           < 10 pixels
Oscillation:           Low (Kd adjustment)
Recovery Time:         < 1 second
Motor Current:         < 2.5 Amps
```

---

## Configuration Examples

### Conservative (Poor Lighting)
```python
follower.set_strategy(LineFollowingStrategy.CONSERVATIVE)
# Kp=0.4, Ki=0.08, Kd=0.2 (smooth, slow)
```

### Balanced (Normal)
```python
follower.set_strategy(LineFollowingStrategy.BALANCED)
# Kp=0.8, Ki=0.15, Kd=0.4 (recommended default)
```

### Aggressive (Perfect Conditions)
```python
follower.set_strategy(LineFollowingStrategy.AGGRESSIVE)
# Kp=1.5, Ki=0.3, Kd=0.8 (fast, responsive)
```

### Custom Tuning
```python
follower.pid_cross_track.set_gains(kp=0.75, ki=0.12, kd=0.38)
```

---

## Troubleshooting Checklist

| Problem | Solution |
|---------|----------|
| **Oscillates** | ↓ Decrease Kp or ↑ Increase Kd |
| **Slow response** | ↑ Increase Kp or use AGGRESSIVE |
| **No recovery** | ↑ Increase Ki |
| **Jerky movements** | ↓ Decrease motor acceleration |
| **Low detection** | ↓ Lower quality_threshold |
| **Poor line detect** | Calibrate HSV ranges |
| **Gets stuck** | Use HYBRID avoidance strategy |
| **Motor overcurrent** | ↓ Reduce acceleration or increase current limit |

---

## Key Metrics to Monitor

```python
# Line Follower
detection_rate      # Should be > 90%
cte_avg            # Should be < 15 pixels
cte_std            # Should be < 10 pixels

# Obstacle Avoider
collision_count     # Should be 0
avoidance_maneuvers # Should be reasonable

# Motor Controller
average_current     # Should be < 2.0A
current_limit_events # Should be 0
max_speed          # Should be smooth ramp
```

---

## Files Location

```
📄 API Usage:       src/control/
📚 Documentation:   CONTROL_TUNING_GUIDE.md
🎓 Examples:        CONTROL_EXAMPLES.py
🔍 Details:         MOTOR_CONTROL_OPTIMIZATION.md
```

---

**Quick Start:** See CONTROL_EXAMPLES.py for runnable code!

**Need Help?** Check CONTROL_TUNING_GUIDE.md section "Troubleshooting"
