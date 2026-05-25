"""
Practical Examples: Using Advanced Control Algorithms
Demonstrates real-world usage of PID line follower, obstacle avoider, and motor controller.
"""

import cv2
import numpy as np
import time
from typing import Optional

# Import new control modules
from src.control import (
    LineFollower, LineFollowingStrategy,
    ObstacleAvoider, AvoidanceStrategy, ObstacleData,
    MotorController, MotorControlMode
)
from src.utils import RateLimiter, LifecycleLogger


# ============================================================================
# EXAMPLE 1: Basic Line Following with PID
# ============================================================================

def example_1_basic_line_following():
    """
    Simple line following using PID controller.
    Robot follows a red line at constant speed.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Line Following with PID")
    print("="*70)
    
    # Initialize
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("ERROR: Cannot open camera")
        return
    
    follower = LineFollower(
        frame_width=640,
        frame_height=480,
        strategy=LineFollowingStrategy.BALANCED
    )
    
    print("\nStarting line following...")
    print("- Strategy: BALANCED")
    print("- PID Gains: Kp=0.8, Ki=0.15, Kd=0.4")
    print("- Press 'q' to quit\n")
    
    frame_count = 0
    start_time = time.time()
    
    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                break
            
            # Detect line
            detection = follower.detect_line(frame)
            
            # Calculate control output
            control = follower.calculate_control(detection, forward_speed=0.5)
            
            # Display results on frame
            status = f"Detected: {'YES' if detection.detected else 'NO'}"
            quality = f"Quality: {detection.quality_score:.1f}/100"
            forward = f"Forward: {control.velocity_forward:.2f}"
            turn = f"Turn: {control.angular_velocity:.2f}"
            
            cv2.putText(frame, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, 
                       (0, 255, 0) if detection.detected else (0, 0, 255), 2)
            cv2.putText(frame, quality, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                       (255, 255, 0), 2)
            cv2.putText(frame, forward, (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                       (0, 255, 255), 2)
            cv2.putText(frame, turn, (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                       (255, 0, 255), 2)
            
            # Draw frame center
            cv2.circle(frame, (320, 240), 5, (0, 255, 0), -1)
            
            if detection.detected:
                # Draw detected center
                cv2.circle(frame, (int(detection.center_x), int(detection.center_y)), 
                          5, (255, 0, 0), -1)
                cv2.rectangle(frame, 
                            (detection.bounding_box[0], detection.bounding_box[1]),
                            (detection.bounding_box[0] + detection.bounding_box[2],
                             detection.bounding_box[1] + detection.bounding_box[3]),
                            (255, 0, 0), 2)
            
            cv2.imshow('Line Following', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            frame_count += 1
        
        # Print statistics
        elapsed = time.time() - start_time
        metrics = follower.get_performance_metrics()
        
        print(f"\n✅ Line Following Complete")
        print(f"Frames processed: {frame_count}")
        print(f"Duration: {elapsed:.1f}s")
        print(f"FPS: {frame_count/elapsed:.1f}")
        print(f"Detection rate: {metrics['detection_rate']:.1f}%")
        print(f"Cross-track error (avg): {metrics['cte_avg']:.2f} pixels")
        print(f"Cross-track error (std): {metrics['cte_std']:.2f} pixels")
        
    finally:
        camera.release()
        cv2.destroyAllWindows()


# ============================================================================
# EXAMPLE 2: Adaptive Strategy Selection
# ============================================================================

def example_2_adaptive_strategy():
    """
    Line following with automatic strategy adaptation.
    Strategy switches based on line quality.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Adaptive Strategy Selection")
    print("="*70)
    
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        return
    
    follower = LineFollower(strategy=LineFollowingStrategy.CONSERVATIVE)
    
    print("\nAdaptive strategy in action:")
    print("- Quality < 30: CONSERVATIVE (smooth, stable)")
    print("- Quality 30-60: BALANCED (normal)")
    print("- Quality > 60: AGGRESSIVE (fast response)")
    print("- Press 'q' to quit\n")
    
    quality_history = []
    
    try:
        frame_count = 0
        while frame_count < 500:
            ret, frame = camera.read()
            if not ret:
                break
            
            detection = follower.detect_line(frame)
            quality_history.append(detection.quality_score)
            
            # Adapt every 50 frames
            if frame_count % 50 == 0 and len(quality_history) > 0:
                avg_quality = np.mean(quality_history[-50:])
                follower.adapt_strategy(avg_quality)
                
                strategy_name = follower.strategy.value.upper()
                print(f"Frame {frame_count}: Quality={avg_quality:.1f} → Strategy={strategy_name}")
            
            control = follower.calculate_control(detection, forward_speed=0.5)
            
            # Display current strategy
            strategy_colors = {
                LineFollowingStrategy.CONSERVATIVE: (0, 255, 0),   # Green
                LineFollowingStrategy.BALANCED: (0, 255, 255),     # Yellow
                LineFollowingStrategy.AGGRESSIVE: (0, 0, 255),     # Red
            }
            
            cv2.putText(frame, f"Strategy: {follower.strategy.value.upper()}", 
                       (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1,
                       strategy_colors[follower.strategy], 2)
            
            cv2.imshow('Adaptive Strategy', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            frame_count += 1
        
        print(f"\n✅ Adaptive strategy test complete ({frame_count} frames)")
        
    finally:
        camera.release()
        cv2.destroyAllWindows()


# ============================================================================
# EXAMPLE 3: Obstacle Avoidance with Multiple Strategies
# ============================================================================

def example_3_obstacle_avoidance():
    """
    Simulate obstacle avoidance with different strategies.
    Shows how to switch between strategies based on sensor data.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Obstacle Avoidance Strategies")
    print("="*70)
    
    avoider = ObstacleAvoider(
        strategy=AvoidanceStrategy.WALL_FOLLOWING,
        critical_distance=0.3,
        safe_distance=0.5
    )
    
    print("\nTesting avoidance strategies:")
    print("- WALL_FOLLOWING: Maintain constant wall distance")
    print("- POTENTIAL_FIELD: Virtual forces")
    print("- RANDOM_WALK: Escape tight corners")
    print("- HYBRID: Automatic switching\n")
    
    # Simulate sensor scenarios
    scenarios = [
        ("Open space", 2.0, 1.5, 1.5, None),
        ("Narrow corridor", 0.4, 0.3, 0.3, 2.0),
        ("Tight corner", 0.25, 0.2, 0.2, 2.0),
        ("Obstacle ahead", 0.35, 0.8, 0.7, 2.0),
    ]
    
    for scenario_name, front, left, right, rear in scenarios:
        print(f"\nScenario: {scenario_name}")
        print(f"  Distances - Front: {front:.2f}m, Left: {left:.2f}m, Right: {right:.2f}m")
        
        sensor_data = ObstacleData(front, left, right, rear, time.time())
        
        # Test each strategy
        for strategy in [AvoidanceStrategy.WALL_FOLLOWING, 
                        AvoidanceStrategy.POTENTIAL_FIELD,
                        AvoidanceStrategy.RANDOM_WALK]:
            
            avoider.set_strategy(strategy)
            command = avoider.calculate_avoidance(sensor_data)
            
            print(f"  {strategy.value:18} → Forward: {command.linear_velocity:6.2f}, "
                  f"Turn: {command.angular_velocity:6.2f}, "
                  f"Obstacle: {command.obstacle_detected}")
    
    print("\n✅ Obstacle avoidance demo complete")


# ============================================================================
# EXAMPLE 4: Motor Control with Smooth Ramping
# ============================================================================

def example_4_motor_control_ramping():
    """
    Demonstrate smooth acceleration ramping.
    Shows how acceleration profiles affect motor behavior.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Motor Control with Smooth Ramping")
    print("="*70)
    
    motors = MotorController(num_motors=4)
    
    print("\nDemonstrating smooth acceleration profiles:\n")
    
    # Profile 1: Fast acceleration
    print("Profile 1: FAST Acceleration (Kp=2.0)")
    motors.accelerations = [2.0, 2.0, 2.0, 2.0]
    motors.set_target_speed([0, 1, 2, 3], [0.8, 0.8, 0.8, 0.8])
    
    for step in range(5):
        motors.update()
        speeds = motors.get_current_speeds()
        print(f"  Step {step}: {speeds}")
    
    motors.stop_all_motors()
    
    # Profile 2: Normal acceleration
    print("\nProfile 2: NORMAL Acceleration (Kp=0.5)")
    motors.accelerations = [0.5, 0.5, 0.5, 0.5]
    motors.set_target_speed([0, 1, 2, 3], [0.8, 0.8, 0.8, 0.8])
    
    for step in range(20):
        motors.update()
        if step % 5 == 0:
            speeds = motors.get_current_speeds()
            print(f"  Step {step:2d}: {speeds[0]:.2f}")
    
    motors.stop_all_motors()
    
    # Profile 3: Smooth acceleration
    print("\nProfile 3: SMOOTH Acceleration (Kp=0.2)")
    motors.accelerations = [0.2, 0.2, 0.2, 0.2]
    motors.set_target_speed([0, 1, 2, 3], [0.8, 0.8, 0.8, 0.8])
    
    for step in range(50):
        motors.update()
        if step % 10 == 0:
            speeds = motors.get_current_speeds()
            print(f"  Step {step:2d}: {speeds[0]:.2f}")
    
    print("\n✅ Motor ramping demo complete")
    
    # Show metrics
    metrics = motors.get_performance_metrics()
    print(f"\nMotor Statistics:")
    print(f"  Average speed: {metrics['average_speed']:.2f}")
    print(f"  Max speed: {metrics['max_speed']:.2f}")
    print(f"  Average current: {metrics['average_current']:.2f}A")


# ============================================================================
# EXAMPLE 5: Integrated System (Line Following + Obstacle Avoidance)
# ============================================================================

def example_5_integrated_system():
    """
    Complete integrated system: line follower + obstacle avoider + motor control.
    Shows real-time decision making.
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Integrated Control System")
    print("="*70)
    
    # Initialize all components
    line_follower = LineFollower(strategy=LineFollowingStrategy.BALANCED)
    obstacle_avoider = ObstacleAvoider(strategy=AvoidanceStrategy.WALL_FOLLOWING)
    motor_control = MotorController(num_motors=4)
    rate_limiter = RateLimiter(frequency_hz=20)
    logger = LifecycleLogger()
    
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        return
    
    print("\nIntegrated system running:")
    print("- Line follower: BALANCED strategy")
    print("- Obstacle avoider: WALL_FOLLOWING strategy")
    print("- Motor control: 4-motor differential drive")
    print("- Loop rate: 20 Hz")
    print("- Press 'q' to quit\n")
    
    frame_count = 0
    decisions = {'line_follow': 0, 'obstacle_avoid': 0}
    
    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                break
            
            # STEP 1: Detect line
            detection = line_follower.detect_line(frame)
            
            # STEP 2: Simulate obstacle detection
            # (In real system, read from ultrasonic sensors)
            simulated_front_distance = np.random.uniform(0.5, 2.0)
            sensor_data = ObstacleData(
                front_distance=simulated_front_distance,
                left_distance=np.random.uniform(0.4, 1.5),
                right_distance=np.random.uniform(0.4, 1.5),
                rear_distance=None,
                timestamp=time.time()
            )
            
            # STEP 3: Decision logic
            if detection.detected and detection.quality_score > 40:
                # Good line detected
                if simulated_front_distance > 0.6:
                    # No obstacle, follow line
                    line_control = line_follower.calculate_control(detection)
                    motor_control.set_velocity_command(
                        line_control.velocity_forward,
                        line_control.angular_velocity
                    )
                    decision = "line_follow"
                else:
                    # Obstacle detected, avoid while recovering line
                    avoidance_control = obstacle_avoider.calculate_avoidance(sensor_data)
                    motor_control.set_velocity_command(
                        avoidance_control.linear_velocity,
                        avoidance_control.angular_velocity
                    )
                    decision = "obstacle_avoid"
            else:
                # No line, search using obstacle avoidance
                avoidance_control = obstacle_avoider.calculate_avoidance(sensor_data)
                motor_control.set_velocity_command(
                    avoidance_control.linear_velocity,
                    avoidance_control.angular_velocity
                )
                decision = "obstacle_avoid"
            
            decisions[decision] += 1
            
            # STEP 4: Update motor control
            pwm_values = motor_control.update()
            
            # Display on frame
            cv2.putText(frame, f"Decision: {decision.upper()}", (20, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Line Quality: {detection.quality_score:.1f}", (20, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"Front Dist: {simulated_front_distance:.2f}m", (20, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"Motor PWM: {pwm_values[0]:.2f}", (20, 160),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            
            cv2.imshow('Integrated System', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Maintain loop rate
            rate_limiter.sleep()
            frame_count += 1
            
            # Print metrics every 100 frames
            if frame_count % 100 == 0:
                print(f"Frame {frame_count}: {decisions['line_follow']} line follows, "
                      f"{decisions['obstacle_avoid']} avoidances")
        
        print(f"\n✅ Integrated system demo complete ({frame_count} frames)")
        print(f"Decision breakdown:")
        print(f"  Line following: {decisions['line_follow']} times")
        print(f"  Obstacle avoidance: {decisions['obstacle_avoid']} times")
        
    finally:
        camera.release()
        cv2.destroyAllWindows()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("ADVANCED CONTROL ALGORITHMS - PRACTICAL EXAMPLES")
    print("="*70)
    print("\nAvailable examples:")
    print("1. Basic line following with PID")
    print("2. Adaptive strategy selection")
    print("3. Obstacle avoidance strategies")
    print("4. Motor control ramping")
    print("5. Integrated system (all components)")
    
    choice = input("\nSelect example (1-5): ").strip()
    
    examples = {
        '1': example_1_basic_line_following,
        '2': example_2_adaptive_strategy,
        '3': example_3_obstacle_avoidance,
        '4': example_4_motor_control_ramping,
        '5': example_5_integrated_system,
    }
    
    if choice in examples:
        try:
            examples[choice]()
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
    else:
        print("Invalid choice")
