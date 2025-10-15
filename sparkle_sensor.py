from random import uniform
import math
import plasma
import time
import machine

"""
A festive sparkly effect. Play around with BACKGROUND_COLOUR and SPARKLE_COLOUR for different effects!
"""
frame = 0
# Set how many LEDs you have
NUM_LEDS = 120

# How many sparkles? [bigger number = more sparkles]
SPARKLE_INTENSITY = 0.005

# Change your colours here! RGB colour picker: https://g.co/kgs/k2Egjk
# BACKGROUND_COLOUR = [50, 50, 0]
BACKGROUND_COLOUR = [0, 50, 0]
SPARKLE_COLOUR = [0, 255, 0]

# how quickly current colour changes to target colour [1 - 255]
FADE_UP_SPEED = 2
FADE_DOWN_SPEED = 2

TRIG = machine.Pin(27, machine.Pin.OUT)   
ECHO = machine.Pin(28, machine.Pin.IN)  # (with voltage divider)
last_distance = 45.0

distance = 50.0
def display_current():
    global distance, frame
    if (frame % 10):
        print ("Getting new distance")
        distance = get_distance()
    if distance >= 1000:
        distance = 400.0
    
    t = 1 - (distance - 22) / 400
    print ("t: ", t)
    # paint our current LED colours to the strip
    for i in range(NUM_LEDS):
        #led_strip.set_rgb(i, current_leds[i][0], current_leds[i][1], current_leds[i][2])
        #led_strip.set_rgb(i, int(current_leds[i][0] * t), int(current_leds[i][1] * t), int(current_leds[i][2] * t))
        # led_strip.set_hsv(i, 0.5, 1.0, t)
        led_strip.set_hsv(i, 0.1, 1.0, t)


def move_to_target():
    # nudge our current colours closer to the target colours
    for i in range(NUM_LEDS):
        for c in range(3):  # 3 times, for R, G & B channels
            if current_leds[i][c] < target_leds[i][c]:
                current_leds[i][c] = min(current_leds[i][c] + FADE_UP_SPEED, target_leds[i][c])  # increase current, up to a maximum of target
            elif current_leds[i][c] > target_leds[i][c]:
                current_leds[i][c] = max(current_leds[i][c] - FADE_DOWN_SPEED, target_leds[i][c])  # reduce current, down to a minimum of target

def get_distance():
    global last_distance
    # Ensure trigger is low
    TRIG.value(0)
    time.sleep_us(2)

    # Send 10 µs HIGH pulse to trigger
    TRIG.value(1)
    time.sleep_us(10)
    TRIG.value(0)

    # Measure echo pulse width (timeout = 30 ms)
    try:
        duration = machine.time_pulse_us(ECHO, 1, 30000)  # microseconds
    except OSError:  # timeout
        return None

    # Convert time to distance
    # Sound speed ~343 m/s → 29.1 µs per cm round-trip
    distance_cm = (duration / 2) / 29.1

    if (distance_cm < 22.7):
        distance_cm = 1000.0

    print("Distance: ", distance_cm)
    return distance_cm


# Create a list of [r, g, b] values that will hold current LED colours, for display
current_leds = [[0] * 3 for i in range(NUM_LEDS)]
# Create a list of [r, g, b] values that will hold target LED colours, to move towards
target_leds = [[0] * 3 for i in range(NUM_LEDS)]

# set up the WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_RGB)

# start updating the LED strip
led_strip.start()

while True:
    time.sleep(0.5)

   
    display_current()  # display current colours to strip
    frame+=1
