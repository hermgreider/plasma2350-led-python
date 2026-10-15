import gc
import time
import plasma
from pimoroni import RGBLED
from daisy_link import DaisyLink
from arpeggiator import Arpeggiator

"""
Plays the "Drone with Lead" demo on the Daisy over I2C, and lights the LED
strip in sync with every note.

The arpeggio on channel 1 runs here (lib/arpeggiator.py), not on the Daisy:
the script selects program #12, #11 without the Daisy's arpeggiator, and
each arp step goes out as a plain note. That way the Plasma knows every note
that sounds.

LEDs: the strip is split evenly, one zone per voice (MIDI channel), each
zone split evenly into SLOTS slots -- see VOICES. A note lights one slot in
its voice's color for as long as it sounds:
  arpeggio  the slot is the note's place in the held chord, so steps march
            up the zone
  others    the first free slot when the note starts

Each pass of the main loop sends whatever MIDI is due, sets only the LEDs
that changed, and pushes the strip out right away (no 60fps timer), so a
note's light starts leaving the Plasma within a millisecond or two of the
note itself.

Every STATS_INTERVAL_MSEC it prints, avg/max in ms over the interval:
  late   a script event or clock tick was sent after it was due
  light  from the first MIDI sent in a pass to the strip push starting
  gap    between main-loop passes -- the worst-case wait for any event
  gc     the gc.collect() run when the loop is idle

Onboard LED:
  red      waiting for the Daisy to answer
  green    connected, playing
  magenta  the Daisy answered with a different protocol version

Needs lib/daisy_link.py and lib/arpeggiator.py on the board, then:
  mpremote run demo_player.py
"""

# Clock tempo. The arpeggio steps on this clock.
TEMPO_BPM = 60

# Let the Daisy's "connected" phrase finish before taking over
AFTER_CONNECT_MSEC = 1500

# How often to print link counters and loop timing
STATS_INTERVAL_MSEC = 10_000

NUM_LEDS = 288

# Caps every LED. At most a third of the strip is lit at once here, so this
# stays well inside the Mac's 3A.
BRIGHTNESS = 0.25

# Each voice's zone is split into this many slots
SLOTS = 4
ZONE_LEDS = 96
SLOT_LEDS = ZONE_LEDS // SLOTS

# MIDI channel -> (hue, first LED of its zone)
VOICES = {
    1: (300 / 360, 0),  # arpeggio: magenta, LEDs 0-95
    0: (230 / 360, 96),  # drone: blue, LEDs 96-191
    2: (180 / 360, 192),  # flute: cyan, LEDs 192-287
}

# The channel whose notes go through the arpeggiator rather than straight
# to the Daisy, and its step length in clock ticks (6 = 1/16 notes)
ARP_CHANNEL = 1
ARP_TICKS_PER_STEP = 6

# Collect garbage once the loop has been quiet for GC_IDLE_MSEC -- right
# after a clock tick, with ~40ms to the next one at 60 BPM -- and at most
# every GC_INTERVAL_MSEC. A collection then rarely lands between a note and
# its light.
GC_IDLE_MSEC = 5
GC_INTERVAL_MSEC = 100

NOTE_ON = 0
NOTE_OFF = 1
PROGRAM = 2

# (time ms, kind, channel, data1, data2) -- a port of kDroneLeadScript,
# selecting #12 instead of #11. Keep it in time order: the player only reads forward.
SCRIPT = (
    (0, PROGRAM, 0, 12, 0),

    # Short test note, then 5s of silence
    (200, NOTE_ON, 0, 60, 100),
    (500, NOTE_OFF, 0, 60, 0),

    (5500, NOTE_ON, 0, 48, 90),
    (5500, NOTE_ON, 0, 68, 80),

    (8000, NOTE_OFF, 0, 48, 0),
    (9500, NOTE_ON, 0, 55, 80),

    (12500, NOTE_OFF, 0, 68, 0),
    (14000, NOTE_ON, 0, 63, 80),

    (14000, NOTE_ON, 1, 60, 60),
    (14000, NOTE_ON, 1, 67, 60),
    (14000, NOTE_ON, 1, 75, 60),
    (14000, NOTE_ON, 1, 80, 60),

    (17000, NOTE_OFF, 0, 55, 0),
    (18200, NOTE_ON, 2, 67, 120),
    (18500, NOTE_ON, 0, 48, 80),

    (18700, NOTE_OFF, 2, 67, 0),
    (19500, NOTE_ON, 2, 78, 115),
    (19800, NOTE_OFF, 2, 78, 0),
    (20500, NOTE_ON, 2, 80, 110),
    (20700, NOTE_OFF, 2, 80, 0),
    (21000, NOTE_ON, 2, 78, 115),
    (21200, NOTE_OFF, 2, 78, 0),

    (21500, NOTE_OFF, 0, 63, 0),
    (23000, NOTE_ON, 0, 68, 80),

    (23500, NOTE_OFF, 1, 80, 0),
    (23500, NOTE_ON, 1, 63, 60),

    (24000, NOTE_ON, 2, 80, 50),
    (24500, NOTE_OFF, 2, 80, 0),
    (25500, NOTE_ON, 2, 68, 50),
    (26000, NOTE_OFF, 2, 68, 0),

    (26000, NOTE_OFF, 0, 48, 0),
    (27500, NOTE_ON, 0, 55, 80),

    (30500, NOTE_OFF, 0, 68, 0),
    (32000, NOTE_ON, 0, 63, 80),

    (33500, NOTE_OFF, 0, 55, 0),
    (35000, NOTE_ON, 0, 48, 80),

    (36500, NOTE_OFF, 0, 63, 0),
)


class Timing:
    """avg/max of a set of samples, in microseconds."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.total = 0
        self.count = 0
        self.max = 0

    def add(self, us):
        self.total += us
        self.count += 1
        if us > self.max:
            self.max = us

    def report(self, name):
        avg = self.total / self.count / 1000 if self.count else 0
        return "{} {:.1f}/{:.1f}".format(name, avg, self.max / 1000)


# Which note each slot of each voice is showing, or None
slot_notes = {channel: [None] * SLOTS for channel in VOICES}

# Set when LEDs changed and the strip needs pushing out
strip_dirty = False


def light_slot(channel, slot, on):
    global strip_dirty
    hue, zone_start = VOICES[channel]
    first = zone_start + slot * SLOT_LEDS
    for i in range(first, first + SLOT_LEDS):
        if on:
            strip.set_hsv(i, hue, 1.0, BRIGHTNESS)
        else:
            strip.set_rgb(i, 0, 0, 0)
    strip_dirty = True


def pick_slot(channel, note):
    slots = slot_notes[channel]
    if channel == ARP_CHANNEL:
        return arp.step_index % SLOTS
    for slot in range(SLOTS):
        if slots[slot] is None:
            return slot
    # All taken: share one rather than drop the light
    return note % SLOTS


def play(channel, note, velocity):
    link.note_on(channel, note, velocity)
    if channel in VOICES:
        slot = pick_slot(channel, note)
        slot_notes[channel][slot] = note
        light_slot(channel, slot, True)


def release(channel, note):
    link.note_off(channel, note)
    if channel in VOICES:
        slots = slot_notes[channel]
        for slot in range(SLOTS):
            if slots[slot] == note:
                slots[slot] = None
                light_slot(channel, slot, False)


def send(event):
    _, kind, channel, data1, data2 = event
    if kind == NOTE_ON:
        if channel == ARP_CHANNEL:
            arp.note_on(data1, data2)
        else:
            play(channel, data1, data2)
    elif kind == NOTE_OFF:
        if channel == ARP_CHANNEL:
            arp.note_off(data1)
        else:
            release(channel, data1)
    elif kind == PROGRAM:
        link.program_change(channel, data1)


led = RGBLED("LED_R", "LED_G", "LED_B")
link = DaisyLink()

# No start(): the strip is pushed out by hand, right after each change
strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)
strip.clear()
strip.update()

arp = Arpeggiator(lambda note, velocity: play(ARP_CHANNEL, note, velocity),
                  lambda note: release(ARP_CHANNEL, note),
                  ARP_TICKS_PER_STEP)

print("Connecting to the Daisy...")
while True:
    result = link.connect()
    if result is True:
        led.set_rgb(0, 255, 0)
        print("Connected")
        break
    if result is False:
        led.set_rgb(255, 0, 255)
        print("Daisy speaks a different protocol version -- playing anyway")
        break
    led.set_rgb(255, 0, 0)
    time.sleep_ms(500)

time.sleep_ms(AFTER_CONNECT_MSEC)

late_time = Timing()
light_time = Timing()
gap_time = Timing()
gc_time = Timing()

# 24 pulses per quarter note. Each pulse's due time is computed from a fixed
# start rather than accumulated, so the clock never drifts.
clock_tick_us = 60_000_000 / (TEMPO_BPM * 24)
clock_start = time.ticks_us()
clock_ticks = 0

script_start = time.ticks_ms()
next_event = 0

next_stats = time.ticks_add(time.ticks_ms(), STATS_INTERVAL_MSEC)
last_pass = time.ticks_us()
last_activity = time.ticks_ms()
last_gc = time.ticks_ms()

while True:
    pass_start = time.ticks_us()
    gap_time.add(time.ticks_diff(pass_start, last_pass))
    last_pass = pass_start
    sent = False

    # 1. MIDI: clock ticks (which may step the arpeggio), then script events

    clock_elapsed = time.ticks_diff(pass_start, clock_start)
    while clock_elapsed >= (clock_ticks + 1) * clock_tick_us:
        link.clock()
        arp.on_clock_tick()
        late_time.add(int(clock_elapsed - (clock_ticks + 1) * clock_tick_us))
        clock_ticks += 1
        sent = True

    now = time.ticks_ms()
    elapsed = time.ticks_diff(now, script_start)
    while next_event < len(SCRIPT) and elapsed >= SCRIPT[next_event][0]:
        event = SCRIPT[next_event]
        send(event)
        late_time.add((elapsed - event[0]) * 1000)
        next_event += 1
        sent = True

    # Loop back to the top once every event has fired
    if next_event >= len(SCRIPT):
        next_event = 0
        script_start = now

    # 2. Push out whatever LEDs those notes changed. If the previous push
    # is still going, the next pass catches it.

    if strip_dirty and not strip.is_busy():
        strip.update()
        strip_dirty = False
        light_time.add(time.ticks_diff(time.ticks_us(), pass_start))

    if sent:
        last_activity = now
    elif (time.ticks_diff(now, last_activity) >= GC_IDLE_MSEC
          and time.ticks_diff(now, last_gc) >= GC_INTERVAL_MSEC):
        gc_start = time.ticks_us()
        gc.collect()
        gc_time.add(time.ticks_diff(time.ticks_us(), gc_start))
        last_gc = now

    if time.ticks_diff(now, next_stats) >= 0:
        next_stats = time.ticks_add(next_stats, STATS_INTERVAL_MSEC)
        print(late_time.report("late"), light_time.report("light"),
              gap_time.report("gap"), gc_time.report("gc"),
              "| retries", link.retries, "failures", link.failures,
              "daisy packets", link.packets_received())
        for t in (late_time, light_time, gap_time, gc_time):
            t.reset()

        # Don't count the print and status read against the next gap
        last_pass = time.ticks_us()
