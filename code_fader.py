import time

from machine import Pin
import plasma

UPDATE_INTERVAL = 120  # refresh interval in secs. Be nice to free APIs!

# Set how many LEDs you have
NUM_LEDS = 90

# Set the brightness
BRIGHTNESS = 1.0

# set up the Pico W's onboard LED
pico_led = Pin("LED", Pin.OUT)

# set up the WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_RGB)

# start updating the LED strip
led_strip.start()


class LoopFader:
    def __init__(self, palette):
        self.palette = palette
        self.index = 0

    @property
    def color(self):
        color = self.palette[self.index]
        self.index += 1
        if self.index > len(self.palette)-1:
            self.index = 0
        return color

green_to_off = (19456, 15360, 11520, 8448, 6144, 4096, 2560, 1536, 768, 256, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

pastels = (4983563, 4986133, 4989988, 4995128, 4738120, 3230769, 2051103, 1199122, 936974, 1723418, 2772010, 4148287, 4144972, 
    2763340, 1710668, 921164, 1184332, 2039628, 3223884, 4737100, 4995128, 4989988, 4986133, 4983563)

halloween = (4983552, 4458752, 3999232, 3540226, 3146500, 2753032, 2359565, 2097172, 1769500, 1507367, 1245236, 1048644, 1048644, 
    1245236, 1507367, 1769500, 2097172, 2359565, 2753032, 3146500, 3540226, 3999232, 4458752, 4983552)


faders = [
    LoopFader(green_to_off),
    LoopFader(pastels),
    LoopFader(green_to_off),
    LoopFader(pastels),
    LoopFader(halloween),
    LoopFader(pastels),
    LoopFader(green_to_off),
    LoopFader(pastels),
    LoopFader(green_to_off),
    LoopFader(halloween)
]

def off():
    rgb.fill((0,0,0))
    rgb.show()

while True:
    off()
    rgb[::] = [f.color for f in faders]
    rgb.write()
    time.sleep(0.1)




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
        led_strip.s 
    print(f"LEDs set to {hex}")

    # sleep
    print(f"Sleeping for {UPDATE_INTERVAL} seconds.")
    time.sleep(UPDATE_INTERVAL)