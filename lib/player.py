import time
from song import NOTE_ON, NOTE_OFF, PROGRAM

"""
Plays a song (see song.py) plus MIDI clock, handing each message to
emit(address, midi bytes). The controller sends what it emits out on the
bus; a node's fallback demo feeds it straight into its own Node. Clock and
Start go to address 0, every node.

The script loops forever. It sends MIDI Start at the top of each pass, and
restarts the clock with it, so every node zeroes its clock count at the same
moment. The clock runs at the song's tempo, 24 pulses per quarter note, each
pulse's due time computed from a fixed start rather than accumulated, so it
never drifts.
"""

CLOCK = b"\xf8"
START = b"\xfa"


def to_midi(event):
    _, _, kind, channel, data1, data2 = event
    channel &= 0x0F
    if kind == NOTE_ON:
        return bytes((0x90 | channel, data1 & 0x7F, data2 & 0x7F))
    if kind == NOTE_OFF:
        return bytes((0x80 | channel, data1 & 0x7F, 0))
    if kind == PROGRAM:
        return bytes((0xC0 | channel, data1 & 0x7F))
    return None


class Player:
    def __init__(self, script, tempo_bpm, emit):
        self.script = script
        self.emit = emit
        self.clock_tick_us = 60_000_000 / (tempo_bpm * 24)

        # How late each event or tick was emitted, in us, for stats
        self.late_us = 0
        self.late_max_us = 0
        self.late_count = 0

        self.restart()

    def restart(self):
        self.clock_start = time.ticks_us()
        self.clock_ticks = 0
        self.script_start = time.ticks_ms()
        self.next_event = 0
        self.need_start = True

    def _late(self, us):
        self.late_us += us
        self.late_count += 1
        if us > self.late_max_us:
            self.late_max_us = us

    def take_late(self):
        """(avg, max) lateness in ms since the last call."""
        avg = self.late_us / self.late_count / 1000 if self.late_count else 0
        result = (avg, self.late_max_us / 1000)
        self.late_us = 0
        self.late_max_us = 0
        self.late_count = 0
        return result

    def tick(self):
        """Emits anything due. Returns True if it emitted anything."""
        emitted = False

        if self.need_start:
            self.need_start = False
            self.emit(0, START)
            emitted = True

        clock_elapsed = time.ticks_diff(time.ticks_us(), self.clock_start)
        while clock_elapsed >= (self.clock_ticks + 1) * self.clock_tick_us:
            self.emit(0, CLOCK)
            self._late(int(clock_elapsed - (self.clock_ticks + 1) * self.clock_tick_us))
            self.clock_ticks += 1
            emitted = True

        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self.script_start)
        script = self.script
        while self.next_event < len(script) and elapsed >= script[self.next_event][0]:
            event = script[self.next_event]
            midi = to_midi(event)
            if midi is not None:
                self.emit(event[1], midi)
            self._late((elapsed - event[0]) * 1000)
            self.next_event += 1
            emitted = True

        # Loop back to the top once every event has fired
        if self.next_event >= len(script):
            self.restart()

        return emitted
