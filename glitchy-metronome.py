import plasma
import time

NUM_LEDS = 288
STEP_TIME = 0.5

# 9 hits over 16 steps
PATTERN = [
    1, 0, 1, 1,
    0, 1, 0, 1,
    1, 0, 1, 0,
    1, 0, 1, 0
]

# HSV values are 0.0 - 1.0
# Magenta / pink — bright
ON_HUE = 0.90
ON_SAT = 1.0
ON_VAL = 1.0

# Cyan / blue — very dim
OFF_HUE = 0.52
OFF_SAT = 1.0
OFF_VAL = 0.10

# Plasma 2350
led_strip = plasma.WS2812(
    NUM_LEDS,
    0,
    0,
    color_order=plasma.COLOR_ORDER_GRB
)

led_strip.start()

while True:

    for step in PATTERN:

        if step:
            hue = ON_HUE
            saturation = ON_SAT
            value = ON_VAL
        else:
            hue = OFF_HUE
            saturation = OFF_SAT
            value = OFF_VAL

        # Set every LED
        for i in range(NUM_LEDS):
            led_strip.set_hsv(
                i,
                hue,
                saturation,
                value
            )

        time.sleep(STEP_TIME)