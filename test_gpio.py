import RPi.GPIO as GPIO
import time

# GPIO pins
RED = 17
GREEN = 27
BLUE = 22

# Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(RED, GPIO.OUT)
GPIO.setup(GREEN, GPIO.OUT)
GPIO.setup(BLUE, GPIO.OUT)

# Initialize PWM (100 Hz)
red_pwm = GPIO.PWM(RED, 100)
green_pwm = GPIO.PWM(GREEN, 100)
blue_pwm = GPIO.PWM(BLUE, 100)

red_pwm.start(0)
green_pwm.start(0)
blue_pwm.start(0)

# Helper to set RGB color (convert 0–255 to 0–100% duty cycle)
def set_rgb_color(r, g, b):
    red_pwm.ChangeDutyCycle((r / 255.0) * 100)
    green_pwm.ChangeDutyCycle((g / 255.0) * 100)
    blue_pwm.ChangeDutyCycle((b / 255.0) * 100)

# Likert color map
likert_colors = {
    5: (0, 255, 0),          # Green
    4: (50, 255, 50),       # Yellow-Green (brighter)
    3: (255, 255, 0),        # Yellow
    2: (255, 69, 0),         # True Orange (reddish-orange)
    1: (255, 0, 0)           # Red
}

try:
    print("Testing Likert colors...")
    for likert in range(5, 0, -1):
        print(f"Likert {likert}")
        r, g, b = likert_colors[likert]
        set_rgb_color(r, g, b)
        time.sleep(1)

    # Turn off LED
    set_rgb_color(0, 0, 0)

finally:
    red_pwm.stop()
    green_pwm.stop()
    blue_pwm.stop()
    GPIO.cleanup()
