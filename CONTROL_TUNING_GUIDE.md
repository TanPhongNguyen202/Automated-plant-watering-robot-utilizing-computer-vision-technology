# Control Algorithms - Tuning & Configuration Guide 🔧

## Table of Contents
1. [PID Tuning for Line Following](#pid-tuning)
2. [Line Follower Configuration](#line-follower-config)
3. [Obstacle Avoider Strategy Selection](#obstacle-avoider-config)
4. [Motor Controller Setup](#motor-controller-setup)
5. [Real-World Scenarios](#scenarios)
6. [Troubleshooting](#troubleshooting)

---

## PID Tuning for Line Following

### Understanding PID Terms

```
Control Output = Kp * error + Ki * ∫error + Kd * de/dt

Where:
- error = line_center - frame_center (cross-track error in pixels)
- Kp = Proportional gain (immediate response to error)
- Ki = Integral gain (accumulates small errors)
- Kd = Derivative gain (predicts future error)
```

### Tuning Process (Ziegler-Nichols Method)

#### Step 1: Start with Conservative Values
```python
from src.control import LineFollower, LineFollowingStrategy

follower = LineFollower(
    strategy=LineFollowingStrategy.CONSERVATIVE
)

# Current gains from CONSERVATIVE strategy:
# Kp=0.4, Ki=0.08, Kd=0.2
```

#### Step 2: Test and Observe Behavior

Run test and observe:
```python
metrics = follower.get_performance_metrics()
print(f"Detection Rate: {metrics['detection_rate']}%")
print(f"CTE (Cross-Track Error): {metrics['cte_avg']:.2f} pixels")
print(f"CTE Std Dev: {metrics['cte_std']:.2f}")

# Ideal: High detection rate, low CTE, low CTE_std
```

#### Step 3: Adjust Kp (Proportional Gain)

**If:** Oscillating too much (high CTE_std)
```python
# Decrease Kp
# CONSERVATIVE → Try Kp=0.3
# Or use: follower.pid_cross_track.set_gains(kp=0.3)
```

**If:** Not responding fast enough to errors
```python
# Increase Kp
# CONSERVATIVE → Try Kp=0.5
# Or use: follower.pid_cross_track.set_gains(kp=0.5)
```

#### Step 4: Adjust Ki (Integral Gain)

**If:** Can't recover from sustained offset
```python
# Increase Ki
# Helps eliminate steady-state error
follower.pid_cross_track.set_gains(ki=0.15)
```

**If:** Oscillations getting worse
```python
# Decrease Ki
# Ki can cause oscillations if too high
follower.pid_cross_track.set_gains(ki=0.05)
```

#### Step 5: Adjust Kd (Derivative Gain)

**If:** System overshoots (oscillates around setpoint)
```python
# Increase Kd
# Kd dampens oscillations
follower.pid_cross_track.set_gains(kd=0.5)
```

**If:** System is too slow to respond
```python
# Decrease Kd
follower.pid_cross_track.set_gains(kd=0.2)
```

---

### Predefined Tuning Profiles

#### Profile 1: Conservative (Smooth, Stable)
```python
follower.set_strategy(LineFollowingStrategy.CONSERVATIVE)
# Kp=0.4, Ki=0.08, Kd=0.2
# Use when: Poor line quality, narrow lines, outdoor (lighting changes)
```

#### Profile 2: Balanced (Normal Operation)
```python
follower.set_strategy(LineFollowingStrategy.BALANCED)
# Kp=0.8, Ki=0.15, Kd=0.4
# Use when: Good line quality, indoor, normal speed
```

#### Profile 3: Aggressive (Fast Response)
```python
follower.set_strategy(LineFollowingStrategy.AGGRESSIVE)
# Kp=1.5, Ki=0.3, Kd=0.8
# Use when: Perfect line quality, high speed needed
```

#### Profile 4: Custom Tuning
```python
# After manual tuning, set custom gains
follower.pid_cross_track.set_gains(
    kp=0.75,
    ki=0.12,
    kd=0.38
)
```

---

## Line Follower Configuration

### Basic Setup
```python
from src.control import LineFollower, LineFollowingStrategy

follower = LineFollower(
    frame_width=640,
    frame_height=480,
    strategy=LineFollowingStrategy.BALANCED
)
```

### HSV Color Range Adjustment

For different red line colors:

```python
# Current (standard red):
# lower_red1 = [0, 120, 70]
# upper_red1 = [10, 255, 255]
# lower_red2 = [170, 120, 70]
# upper_red2 = [180, 255, 255]

# For darker red lines:
follower.lower_red1 = np.array([0, 100, 50])
follower.lower_red2 = np.array([170, 100, 50])

# For brighter red lines:
follower.upper_red1 = np.array([15, 255, 255])
follower.upper_red2 = np.array([180, 255, 255])
```

### Adjust Detection Sensitivity

```python
# Minimum line area (pixels²) to consider valid
follower.min_contour_area = 500  # Default

# Stricter detection:
follower.min_contour_area = 1000  # Ignores small artifacts

# More sensitive:
follower.min_contour_area = 200   # Picks up thin lines
```

### Quality Threshold

```python
# Minimum quality score (0-100) for valid detection
follower.quality_threshold = 30.0  # Default

# Stricter:
follower.quality_threshold = 50.0  # Only clear, strong lines

# Lenient:
follower.quality_threshold = 20.0  # Accepts poor quality
```

### Adaptive Tuning

```python
# Automatically adjust strategy based on line quality
# Call periodically (e.g., every 100 iterations)

recent_qualities = [
    m['quality_score'] for m in follower.detection_history.get_all()
]
average_quality = np.mean(recent_qualities)

follower.adapt_strategy(average_quality)
# < 30: CONSERVATIVE
# 30-60: BALANCED  
# > 60: AGGRESSIVE
```

---

## Obstacle Avoider Strategy Selection

### Strategy 1: Wall Following (Recommended)
```python
from src.control import ObstacleAvoider, AvoidanceStrategy

avoider = ObstacleAvoider(
    strategy=AvoidanceStrategy.WALL_FOLLOWING,
    critical_distance=0.3,  # 30cm (stop distance)
    safe_distance=0.5       # 50cm (preferred distance)
)

# Best for: Structured environments, corridors, mazes
# Pros: Smooth motion, predictable path
# Cons: Can't handle open spaces well

# Tuning:
avoider.wall_distance_target = 0.6  # Maintain 60cm from wall
avoider.wall_follow_side = "right"  # Follow right wall
```

### Strategy 2: Potential Field
```python
avoider.set_strategy(AvoidanceStrategy.POTENTIAL_FIELD)

# Best for: Open spaces, multiple obstacles
# Pros: Smooth trajectories, elegant math
# Cons: Can get stuck in local minima

# Tuning:
# Automatic - no parameters needed
```

### Strategy 3: Random Walk
```python
avoider.set_strategy(AvoidanceStrategy.RANDOM_WALK)

# Best for: Unknown environments, emergency backup
# Pros: Simple, never truly stuck
# Cons: Inefficient, random behavior

# Tuning:
avoider.random_walk_duration = 2.0  # Change direction every 2s
avoider.random_walk_direction = np.random.uniform(-90, 90)
```

### Strategy 4: BUG Algorithm
```python
avoider.set_strategy(AvoidanceStrategy.BUG_ALGORITHM)

# Best for: Goal-directed navigation with obstacles
# Pros: Guaranteed to reach goal, optimal path
# Cons: Requires goal position

# Usage:
avoider.target_position = (5.0, 5.0)  # Goal at 5m, 5m
avoider.robot_position = (0, 0)       # Current position
```

### Strategy 5: Hybrid (Auto-Switching)
```python
avoider.set_strategy(AvoidanceStrategy.HYBRID)

# Best for: Dynamic environments
# Pros: Adapts to situation automatically
# Cons: Complex behavior

# Auto-switches between:
# - WALL_FOLLOWING if front < 0.45m
# - POTENTIAL_FIELD if open space > 1.0m
```

---

## Motor Controller Setup

### Basic Configuration
```python
from src.control import MotorController, MotorControlMode, RobotKinematics

# Standard 4-wheel robot
motors = MotorController(
    num_motors=4,
    mode=MotorControlMode.VELOCITY
)

# Custom kinematics
kinematics = RobotKinematics(
    wheel_radius=0.05,          # 5cm wheels
    wheel_separation=0.15,      # 15cm wheelbase
    max_linear_velocity=0.5,    # 50cm/s
    max_angular_velocity=2.0    # 2 rad/s
)

motors = MotorController(
    num_motors=4,
    mode=MotorControlMode.VELOCITY,
    kinematics=kinematics
)
```

### Velocity Control with Smooth Ramping
```python
# Set target velocity
motors.set_velocity_command(
    linear_velocity=0.5,    # 50% forward
    angular_velocity=0.2    # 20% right turn
)

# Motor acceleration is automatically smoothed
# Ramp rate controlled by accelerations array
motors.accelerations = [0.5, 0.5, 0.5, 0.5]  # 0-1 in 2 seconds

# Faster acceleration:
motors.accelerations = [1.5, 1.5, 1.5, 1.5]  # 0-1 in 0.67 seconds

# Smoother acceleration:
motors.accelerations = [0.3, 0.3, 0.3, 0.3]  # 0-1 in 3.3 seconds
```

### Current Limiting
```python
# Set maximum current per motor (Amps)
motors.max_currents = [2.0, 2.0, 2.0, 2.0]

# More conservative (prevent overcurrent):
motors.max_currents = [1.5, 1.5, 1.5, 1.5]

# Less conservative (allow more power):
motors.max_currents = [3.0, 3.0, 3.0, 3.0]

# Monitor current limit events:
metrics = motors.get_performance_metrics()
print(f"Current limit events: {metrics['current_limit_events']}")
```

### Direct Motor Control
```python
# Set individual motor speeds
motors.set_target_speed(
    motor_indices=[0, 1, 2, 3],
    speeds=[0.5, 0.5, 0.5, 0.5],
    accelerations=[0.5, 0.5, 0.5, 0.5]
)

# Different speeds per motor (e.g., turning):
motors.set_target_speed(
    motor_indices=[0, 1, 2, 3],
    speeds=[0.3, 0.7, 0.3, 0.7]  # Inside wheels slower
)

# Get current speeds
current_speeds = motors.get_current_speeds()
print(f"Motor speeds: {current_speeds}")
```

---

## Real-World Scenarios

### Scenario 1: Indoor Line Following

```python
# Setup: Follow red line indoors with obstacles

follower = LineFollower(strategy=LineFollowingStrategy.BALANCED)
avoider = ObstacleAvoider(strategy=AvoidanceStrategy.WALL_FOLLOWING)
motors = MotorController()

for frame in camera_stream:
    # Detect line
    detection = follower.detect_line(frame)
    
    # Read sensors
    sensor_data = read_ultrasonic()
    
    # Decision logic
    if detection.detected and detection.quality_score > 40:
        control = follower.calculate_control(detection, forward_speed=0.4)
        
        # Check for obstacles
        if sensor_data.front_distance > 0.6:
            motors.set_velocity_command(
                control.velocity_forward,
                control.angular_velocity
            )
        else:
            # Obstacle, avoid while maintaining line
            avoidance = avoider.calculate_avoidance(sensor_data)
            motors.set_velocity_command(
                avoidance.linear_velocity,
                avoidance.angular_velocity
            )
    else:
        # No line, search
        motors.set_velocity_command(0.1, 0.3)
    
    speeds = motors.update()
    apply_to_hardware(speeds)
```

### Scenario 2: Outdoor Line Following (Lighting Changes)

```python
# Setup: Adapt to changing lighting conditions

follower = LineFollower(strategy=LineFollowingStrategy.CONSERVATIVE)

# Monitor and adapt
last_quality = 50.0

for frame in camera_stream:
    detection = follower.detect_line(frame)
    
    # Smooth quality estimate
    quality = (last_quality * 0.8 + detection.quality_score * 0.2)
    last_quality = quality
    
    # Auto-adapt strategy
    if quality < 30:
        follower.set_strategy(LineFollowingStrategy.CONSERVATIVE)
    elif quality < 60:
        follower.set_strategy(LineFollowingStrategy.BALANCED)
    else:
        follower.set_strategy(LineFollowingStrategy.AGGRESSIVE)
    
    control = follower.calculate_control(detection, forward_speed=0.3)
    motors.set_velocity_command(control.velocity_forward, control.angular_velocity)
```

### Scenario 3: Maze Navigation

```python
# Setup: Navigate maze with obstacle avoidance

follower = LineFollower()  # Follow line when visible
avoider = ObstacleAvoider(strategy=AvoidanceStrategy.WALL_FOLLOWING)

for iteration in range(max_iterations):
    frame = camera.read()
    sensors = read_sensors()
    
    detection = follower.detect_line(frame)
    
    if detection.detected and detection.quality_score > 50:
        # Line detected, follow it
        control = follower.calculate_control(detection)
        priority = "line"
    else:
        # No line, use obstacle avoidance to explore
        avoidance = avoider.calculate_avoidance(sensors)
        control.velocity_forward = avoidance.linear_velocity
        control.angular_velocity = avoidance.angular_velocity
        priority = "obstacle_avoidance"
    
    motors.set_velocity_command(
        control.velocity_forward,
        control.angular_velocity
    )
    
    speeds = motors.update()
    apply_to_hardware(speeds)
    
    # Log metrics
    if iteration % 50 == 0:
        print(f"Priority: {priority}, "
              f"Obstacle detected: {avoider.calculate_avoidance(sensors).obstacle_detected}")
```

---

## Troubleshooting

### Problem: Line Follower Oscillates (Shaking)

**Cause:** Kp too high or Kd too low

**Solution:**
```python
# Decrease Kp
follower.pid_cross_track.set_gains(kp=0.6)

# Or increase Kd
follower.pid_cross_track.set_gains(kd=0.5)

# Or use conservative strategy
follower.set_strategy(LineFollowingStrategy.CONSERVATIVE)
```

---

### Problem: Line Follower Slow to Respond

**Cause:** Kp too low, or low forward speed

**Solution:**
```python
# Increase Kp
follower.pid_cross_track.set_gains(kp=1.2)

# Or increase forward speed
control = follower.calculate_control(detection, forward_speed=0.6)

# Or use aggressive strategy
follower.set_strategy(LineFollowingStrategy.AGGRESSIVE)
```

---

### Problem: Obstacle Avoider Gets Stuck

**Cause:** Strategy doesn't fit environment

**Solution:**
```python
# Try different strategy
avoider.set_strategy(AvoidanceStrategy.POTENTIAL_FIELD)

# Or use hybrid
avoider.set_strategy(AvoidanceStrategy.HYBRID)

# Adjust critical distance
avoider.critical_distance = 0.4  # More aggressive
```

---

### Problem: Motors Jerking/Not Smooth

**Cause:** Acceleration too high or not ramping

**Solution:**
```python
# Reduce acceleration
motors.accelerations = [0.3, 0.3, 0.3, 0.3]

# Or update more frequently
# (Call motors.update() at higher frequency)
```

---

### Problem: Poor Detection Rate

**Cause:** HSV range wrong or quality threshold too high

**Solution:**
```python
# Lower quality threshold
follower.quality_threshold = 20.0

# Or adjust HSV range
follower.lower_red1 = np.array([0, 100, 60])

# Or increase minimum area
follower.min_contour_area = 300
```

---

## Configuration Checklist

- [ ] PID tuned for line following (Kp, Ki, Kd)
- [ ] HSV ranges calibrated for your red line
- [ ] Line quality threshold appropriate (20-50)
- [ ] Obstacle avoider strategy selected
- [ ] Wall following distance configured (0.5-0.8m)
- [ ] Motor acceleration profiles set
- [ ] Current limits appropriate (1.5-2.5A)
- [ ] Tested indoors first
- [ ] Tested outdoors/lighting conditions
- [ ] Tested with obstacles
- [ ] Performance metrics logged
- [ ] Fallback behaviors defined

---

**Ready to optimize!** 🚀

Follow the tuning process systematically and test incrementally.
