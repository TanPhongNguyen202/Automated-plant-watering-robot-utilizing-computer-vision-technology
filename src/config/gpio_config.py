"""
GPIO Configuration Module
Defines GPIO pin assignments for all hardware components including motors, 
sensors, and control devices.
"""

from gpiozero import (
    DigitalOutputDevice, 
    DigitalInputDevice, 
    PWMOutputDevice, 
    DistanceSensor
)  # type: ignore
from typing import Dict, Any

# ============= Motor Configuration =============
# DC motors with forward, backward, and speed control pins
MOTORS: Dict[str, Dict[str, Any]] = {
    "motor_1": {
        "forward": DigitalOutputDevice(6),
        "backward": DigitalOutputDevice(26),
        "enable": PWMOutputDevice(13)
    },
    "motor_2": {
        "forward": DigitalOutputDevice(16),
        "backward": DigitalOutputDevice(7),
        "enable": PWMOutputDevice(18)
    },
    "motor_3": {
        "forward": DigitalOutputDevice(0),
        "backward": DigitalOutputDevice(1),
        "enable": PWMOutputDevice(12)
    },
    "motor_4": {
        "forward": DigitalOutputDevice(20),
        "backward": DigitalOutputDevice(21),
        "enable": PWMOutputDevice(19)
    }
}

# ============= Ultrasonic Sensor Configuration =============
# Distance sensors with echo and trigger pins
F_SENSOR = DistanceSensor(echo=9, trigger=10)       # Front sensor
F_R_SENSOR = DistanceSensor(echo=15, trigger=14)    # Front-right sensor
F_L_SENSOR = DistanceSensor(echo=24, trigger=23)    # Front-left sensor
L_SENSOR = DistanceSensor(echo=25, trigger=4)       # Left sensor
R_SENSOR = DistanceSensor(echo=22, trigger=8)       # Right sensor

# ============= Relay Configuration =============
# Relay for pump control
RELAY = DigitalOutputDevice(5)

# ============= Water Level Sensor Configuration =============
# Digital input for water level detection
WATER_LEVEL_SENSOR = DigitalInputDevice(pin=11)
