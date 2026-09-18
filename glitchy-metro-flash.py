import plasma
import time
import random

NUM_LEDS = 288
STEP_TIME = 0.5

# 9 over 16 Euclidean rhythm
PATTERN = [
    1, 0, 1, 1,
    0, 1, 0, 1,
    1, 0, 1, 0,
    1, 0, 1, 0
]

# Main colors
ON_HUE = 0.90
ON_SAT = 1.0
ON_VAL = 0.5

OFF_HUE = 0.52
OFF_SAT = 1.0
OFF_VAL = 0.15

# Flicker color - violet
FLICKER_HUE = 0.78
FLICKER_SAT = 1.0
FLICKER_VAL = 0.7


# Plasma 2350
led_strip = plasma.WS2812(
    NUM_LEDS,
    0,
    0,
    color_order=plasma.COLOR_ORDER_GRB
)

led_strip.start()


def beat_color(step):
    if step:
        return ON_HUE, ON_SAT, ON_VAL
    else:
        return OFF_HUE, OFF_SAT, OFF_VAL


def set_beat_color(step):
    hue, sat, val = beat_color(step)

    for i in range(NUM_LEDS):

        # Don't touch the flicker LEDs
        if flicker_active:
            if flicker_start <= i < flicker_start + flicker_length:
                continue

        led_strip.set_hsv(i, hue, sat, val)


def set_flicker_color(on):
    if on:
        hue = FLICKER_HUE
        sat = FLICKER_SAT
        val = FLICKER_VAL
    else:
        # When flicker is off, show the current beat color
        hue, sat, val = beat_color(
            PATTERN[(step_index - 1) % len(PATTERN)]
        )

    for i in range(
        flicker_start,
        flicker_start + flicker_length
    ):
        led_strip.set_hsv(i, hue, sat, val)


# -----------------------------
# State
# -----------------------------

step_index = 0
next_step = time.ticks_ms()

flicker_active = False
flicker_start = 0
flicker_length = 0
flicker_count = 0
flicker_on = False
next_flicker_action = 0

next_flicker = time.ticks_add(
    time.ticks_ms(),
    random.randint(500, 2000)
)


# -----------------------------
# Main loop
# -----------------------------

while True:

    now = time.ticks_ms()

    # -----------------------------
    # Beat
    # -----------------------------

    if time.ticks_diff(now, next_step) >= 0:

        set_beat_color(PATTERN[step_index])

        step_index = (step_index + 1) % len(PATTERN)

        next_step = time.ticks_add(
            next_step,
            int(STEP_TIME * 1000)
        )


    # -----------------------------
    # Start flicker
    # -----------------------------

    if not flicker_active and time.ticks_diff(
        now, next_flicker
    ) >= 0:

        flicker_length = random.randint(15, 20)

        flicker_start = random.randint(
            0,
            NUM_LEDS - flicker_length
        )

        flicker_count = 0
        flicker_active = True
        flicker_on = True

        # First flash
        set_flicker_color(True)

        next_flicker_action = time.ticks_add(
            now,
            random.randint(70, 150)
        )


    # -----------------------------
    # Flicker
    # -----------------------------

    if flicker_active and time.ticks_diff(
        now, next_flicker_action
    ) >= 0:

        if flicker_on:

            # OFF
            set_flicker_color(False)

            flicker_on = False

            next_flicker_action = time.ticks_add(
                now,
                random.randint(70, 150)
            )

        else:

            flicker_count += 1

            if flicker_count >= 3:

                # Finished three flashes
                flicker_active = False

                # Return these LEDs to the beat
                set_beat_color(
                    PATTERN[(step_index - 1) % len(PATTERN)]
                )

                # Wait before next random event
                next_flicker = time.ticks_add(
                    now,
                    random.randint(500, 2000)
                )

            else:

                # Next flash
                flicker_on = True
                set_flicker_color(True)

                next_flicker_action = time.ticks_add(
                    now,
                    random.randint(70, 150)
                )

    time.sleep_ms(5)