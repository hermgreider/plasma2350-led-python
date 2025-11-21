import plasma
import time
import machine

NUM_LEDS = 10
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)
led_strip.start()

LEDS = [(0, 0, 0)] * NUM_LEDS  # preallocate memory

def set_hsv(h, s, v):
    for i in range(NUM_LEDS):
        led_strip.set_hsv(i, h, s, v)

# values = [0.0, 0.33, 0.66, 25.0/360.0, 300.0/ 360.0]
# values = [.51, .52, .561, .562, .563, .95] # Moogy Bass
values = [.1, .15, .175, .4, .85, .87] # Bell 1 pane

while(True):
    for value in values:
        set_hsv(value, 1.0, 0.2)
        time.sleep(0.5);
 
