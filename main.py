import time

from machine import Pin
import plasma

"""
This Plasma Stick example sets your LED strip to the current #cheerlights colour.
Find out more about the Cheerlights API at https://cheerlights.com/
"""

UPDATE_INTERVAL = 120  # refresh interval in secs. Be nice to free APIs!

# Set how many LEDs you have
NUM_LEDS = 90

# Set the brightness
BRIGHTNESS = 1.0

def spooky_rainbows():
    print("SPOOKY RAINBOWS!")
    HUE_START = 30  # orange
    HUE_END = 140  # green
    SPEED = 0.3  # bigger = faster (harder, stronger)

    distance = 0.0
    direction = SPEED
    while True:
        for i in range(NUM_LEDS):
            # generate a triangle wave that moves up and down the LEDs
            j = max(0, 1 - abs(distance - i) / (NUM_LEDS / 3))
            hue = HUE_START + j * (HUE_END - HUE_START)

            led_strip.set_hsv(i, hue / 360, 1.0, BRIGHTNESS)

        # reverse direction at the end of colour segment to avoid an abrupt change
        distance += direction
        if distance > NUM_LEDS:
            direction = - SPEED
        if distance < 0:
            direction = SPEED

        time.sleep(0.01)


def hex_to_rgb(hex):
    # converts a hex colour code into RGB
    h = hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return r, g, b


# set up the Pico W's onboard LED
pico_led = Pin("LED", Pin.OUT)

# set up the WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_RGB)

# start updating the LED strip
led_strip.start()

spooky_rainbows()

while True:

    # flash the onboard LED after getting data
    pico_led.value(True)
    time.sleep(0.2)
    pico_led.value(False)

    # extract hex colour from the data
    hex = j["field2"]

    # and convert it to RGB
    r, g, b = hex_to_rgb(hex)

    # adjust the brightness
    r, g, b = (int(i * BRIGHTNESS) for i in (r, g, b))

    # light up the LEDs
    for i in range(NUM_LEDS):
        led_strip.set_rgb(i, r, g, b)
    print(f"LEDs set to {hex}")

    # sleep
    print(f"Sleeping for {UPDATE_INTERVAL} seconds.")
    time.sleep(UPDATE_INTERVAL)
