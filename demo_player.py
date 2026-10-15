import time
from pimoroni import RGBLED
from daisy_link import DaisyLink

"""
Plays the "Drone with Lead" demo on the Daisy over I2C -- the same script
the Daisy used to play on its own (Portalv2's demo/demo_script.cpp), now
sent from here, along with the MIDI clock its arpeggiator steps on.

Onboard LED:
  red      waiting for the Daisy to answer
  green    connected, playing
  magenta  the Daisy answered with a different protocol version

Needs lib/daisy_link.py on the board (see that file), then:
  mpremote run demo_player.py
"""

# Clock tempo. The arpeggiated Pluck on channel 1 steps on this clock.
TEMPO_BPM = 60

# Let the Daisy's "connected" phrase finish before taking over
AFTER_CONNECT_MSEC = 1500

# How often to print link counters
STATS_INTERVAL_MSEC = 10_000

NOTE_ON = 0
NOTE_OFF = 1
PROGRAM = 2

# (time ms, kind, channel, data1, data2) -- a straight port of
# kDroneLeadScript. Keep it in time order: the player only reads forward.
SCRIPT = (
    (0, PROGRAM, 0, 11, 0),

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


def send(link, event):
    _, kind, channel, data1, data2 = event
    if kind == NOTE_ON:
        link.note_on(channel, data1, data2)
    elif kind == NOTE_OFF:
        link.note_off(channel, data1)
    elif kind == PROGRAM:
        link.program_change(channel, data1)


led = RGBLED("LED_R", "LED_G", "LED_B")
link = DaisyLink()

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

# 24 pulses per quarter note. Each pulse's due time is computed from a fixed
# start rather than accumulated, so the clock never drifts.
clock_tick_us = 60_000_000 / (TEMPO_BPM * 24)
clock_start = time.ticks_us()
clock_ticks = 0

script_start = time.ticks_ms()
next_event = 0

next_stats = time.ticks_add(time.ticks_ms(), STATS_INTERVAL_MSEC)

while True:
    clock_elapsed = time.ticks_diff(time.ticks_us(), clock_start)
    while clock_elapsed >= (clock_ticks + 1) * clock_tick_us:
        link.clock()
        clock_ticks += 1

    now = time.ticks_ms()
    elapsed = time.ticks_diff(now, script_start)
    while next_event < len(SCRIPT) and elapsed >= SCRIPT[next_event][0]:
        send(link, SCRIPT[next_event])
        next_event += 1

    # Loop back to the top once every event has fired
    if next_event >= len(SCRIPT):
        next_event = 0
        script_start = now

    if time.ticks_diff(now, next_stats) >= 0:
        next_stats = time.ticks_add(next_stats, STATS_INTERVAL_MSEC)
        print("retries", link.retries, "failures", link.failures,
              "daisy packets", link.packets_received())

    time.sleep_ms(1)
