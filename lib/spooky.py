"""
Spooky rainbows (from spooky.py): an orange-to-green triangle wave that
sweeps up and down the strip.

Unlike spooky.py, the wave's position is a function of MIDI clock position,
not of how many frames have been drawn. Two boards at the same clock tick
draw the same frame, however fast or slow each one renders.
"""

HUE_START = 30  # orange
HUE_END = 140  # green

# Clock ticks per quarter note, the MIDI standard
TICKS_PER_BEAT = 24


class Spooky:
    def __init__(self, strip, num_leds, brightness, beats_per_sweep):
        self.strip = strip
        self.num_leds = num_leds
        self.brightness = brightness

        # One sweep is one end of the strip to the other; there and back is
        # two
        self.ticks_per_sweep = beats_per_sweep * TICKS_PER_BEAT

    def render(self, tick_pos):
        """Draws the frame for clock position tick_pos (ticks since start,
        fractional between ticks)."""
        n = self.num_leds

        # Triangle wave: 0 -> n over one sweep, then back
        phase = (tick_pos / self.ticks_per_sweep) % 2.0
        distance = n * (phase if phase < 1.0 else 2.0 - phase)

        set_hsv = self.strip.set_hsv
        brightness = self.brightness
        width = n / 3
        hue_start = HUE_START / 360
        hue_span = (HUE_END - HUE_START) / 360

        for i in range(n):
            j = max(0, 1 - abs(distance - i) / width)
            set_hsv(i, hue_start + j * hue_span, 1.0, brightness)
