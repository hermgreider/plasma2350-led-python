
import time
from machine import Pin
import plasma
import math

"""
This Plasma Stick example sets your LED strip to the current #cheerlights colour.
Find out more about the Cheerlights API at https://cheerlights.com/
"""

UPDATE_INTERVAL = 120  # refresh interval in secs. Be nice to free APIs!

# Set how many LEDs you have
NUM_LEDS = 144

# Set the brightness
BRIGHTNESS = 0.2

# Config
NUM_LEDS = 144
BRIGHTNESS = 0.2
SPEED = 0.5  # higher = faster animation
SCALE = 0.2   # lower = smoother pattern

# Two colors
COLOR_A = (252, 186, 3)  
COLOR_B = (165, 252, 3)  

# Setup
pico_led = Pin("LED", Pin.OUT)
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_RGB)
led_strip.start()

# Main animation
def scrolling_perlin():
    print("Scrolling 2-color Perlin noise!")
    offset = 0.0
    while True:
        for i in range(NUM_LEDS):
            # Noise input: LED position + offset
            noise_input = i * SCALE + offset
            t = pseudo_perlin(noise_input)  # range ~ [0,1]

            # Blend between the two colors
            r, g, b = lerp_color(COLOR_A, COLOR_B, t)

            # Apply brightness
            r = int(r * BRIGHTNESS)
            g = int(g * BRIGHTNESS)
            b = int(b * BRIGHTNESS)

            # Set LED color
            led_strip.set_rgb(i, r, g, b)

        # Move the noise pattern upward
        offset += SPEED
        time.sleep(0.01)

def hex_to_rgb(hex):
    # converts a hex colour code into RGB
    h = hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return r, g, b

# Basic smooth noise function using sine (not true Perlin, but gives smooth results)
def pseudo_perlin(x):
    return 0.5 + 0.5 * math.sin(x)

# Blend two RGB colors
def lerp_color(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )

scrolling_perlin()