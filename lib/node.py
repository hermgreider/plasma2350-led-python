import time
from arpeggiator import Arpeggiator

"""
What a portal node does with MIDI, wherever it comes from (the bus, the
controller on the same board, or the node's own fallback demo): plays it on
the Daisy over I2C, runs the arpeggio, and lights the strip in sync.

The arpeggio on ARP_CHANNEL runs here, not on the Daisy, stepping on the
MIDI clock every node receives -- so arpeggios on different boards stay in
step, and the Plasma knows every note that sounds.

MIDI Start (sent when the controller starts and each time its song loops)
releases everything and zeroes the clock count, so a node that missed the
start of the song, or still holds notes from before the controller
restarted, lines up again.

LEDs: the whole strip is split evenly among the voices (MIDI channels) this
node plays, one zone each, and each zone evenly into that voice's slots -- as
many as it ever has notes sounding at once (VOICE_SLOTS), so each note gets
as many LEDs as possible. A note lights one slot in its voice's color
(VOICE_HUES) for as long as it sounds:
  arpeggio  the slot is the note's place in the held chord, so steps march
            up the zone
  pitched   (VOICE_PITCH_RANGES) a PITCH_SECTION_FRACTION-sized section
            placed along the zone by pitch, low notes at the start, so a
            melody moves along the strip
  others    the first free slot when the note starts
Only the changed slot is set, and the strip is pushed out right after the
MIDI that changed it (see push_leds()), not on a frame timer.
"""

NUM_LEDS = 288

# Caps every LED. At most a third of the strip is lit at once, so this stays
# well inside the 3A budget.
BRIGHTNESS = 0.25

# MIDI channel -> hue
VOICE_HUES = {
    1: 300 / 360,  # arpeggio: magenta
    0: 230 / 360,  # drone: blue
    2: 180 / 360,  # flute: cyan
}

# MIDI channel -> (lowest note, highest note): voices whose notes are placed
# along their zone by pitch instead of in slots. Set to the range the song
# actually uses, to spread its notes as far apart as possible.
VOICE_PITCH_RANGES = {
    2: (67, 80),  # flute
}

# A pitched note lights this fraction of its voice's zone
PITCH_SECTION_FRACTION = 4

# MIDI channel -> slots in its zone: the most notes it ever has sounding at
# once. The arpeggio sounds one note at a time, but a slot per held chord
# note lets its steps march along the zone.
VOICE_SLOTS = {
    1: 4,  # arpeggio: up to a 4-note chord
    0: 2,  # drone: two notes overlap
    2: 1,  # flute: one note at a time
}

# Which voices a node plays, in strip order, when node.json doesn't say
DEFAULT_VOICES = (1, 0, 2)

# The channel whose notes go through the arpeggiator, and its step length in
# clock ticks (6 = 1/16 notes)
ARP_CHANNEL = 1
ARP_TICKS_PER_STEP = 6


def _message_length(status):
    """Bytes in a MIDI message with this status byte, including it."""
    high = status & 0xF0
    if high in (0xC0, 0xD0):
        return 2
    if high < 0xF0:
        return 3
    # System messages: only real-time (single byte) are expected
    return 1


class Node:
    def __init__(self, link, strip, voices=DEFAULT_VOICES):
        """voices lists the MIDI channels this node plays, in the order
        their zones run along the strip."""
        self.link = link
        self.strip = strip

        # MIDI channel -> (hue, first LED of its zone, slots, LEDs per slot)
        zone_leds = NUM_LEDS // len(voices)
        self.voices = {}
        for i, channel in enumerate(voices):
            slots = VOICE_SLOTS[channel]
            self.voices[channel] = (VOICE_HUES[channel], i * zone_leds, slots, zone_leds // slots)

        self.arp = Arpeggiator(
            lambda note, velocity: self._play(ARP_CHANNEL, note, velocity),
            lambda note: self._release(ARP_CHANNEL, note),
            ARP_TICKS_PER_STEP)

        # Notes sounding on the Daisy, per channel
        self.sounding = {channel: set() for channel in range(16)}

        # Which note each slot of each voice is showing, or None
        self.slot_notes = {channel: [None] * voice[2] for channel, voice in self.voices.items()}

        # Pitched voices: channel -> {note: first LED of its section}
        self.pitched = {channel: {} for channel in self.voices if channel in VOICE_PITCH_RANGES}

        # Set when LEDs changed and the strip needs pushing out
        self.strip_dirty = False

        # Clock ticks since the last MIDI Start
        self.clock_count = 0

    def handle(self, payload):
        """Plays one or more complete MIDI messages."""
        i = 0
        while i < len(payload):
            status = payload[i]
            length = _message_length(status)
            self._handle_message(status, payload[i + 1:i + length])
            i += length

    def all_off(self):
        """Stops every note this node started, and the arpeggio."""
        self.arp.reset()
        for channel in range(16):
            for note in list(self.sounding[channel]):
                self._release(channel, note)

    def push_leds(self):
        """Pushes the strip out if anything changed. Returns True if it did.
        If the previous push is still going, the next call catches it."""
        if self.strip_dirty and not self.strip.is_busy():
            self.strip.update()
            self.strip_dirty = False
            return True
        return False

    def _handle_message(self, status, data):
        kind = status & 0xF0
        channel = status & 0x0F

        if status == 0xF8:
            self.clock_count += 1
            self.link.clock()
            self.arp.on_clock_tick(self.clock_count)
        elif status == 0xFA:
            self.all_off()
            self.clock_count = 0
        elif kind == 0x90 and data[1] > 0:
            if channel == ARP_CHANNEL:
                self.arp.note_on(data[0], data[1])
            else:
                self._play(channel, data[0], data[1])
        elif kind == 0x80 or kind == 0x90:
            if channel == ARP_CHANNEL:
                self.arp.note_off(data[0])
            else:
                self._release(channel, data[0])
        elif kind == 0xC0:
            # The Daisy drops every voice when it loads a program; let go of
            # the notes here too, so no light stays on for a silent note
            self.all_off()
            self.link.program_change(channel, data[0])

    def _play(self, channel, note, velocity):
        self.link.note_on(channel, note, velocity)
        self.sounding[channel].add(note)
        if channel in self.pitched:
            first, count = self._pitch_section(channel, note)
            self.pitched[channel][note] = first
            self._light(channel, first, count, True)
        elif channel in self.voices:
            slot = self._pick_slot(channel, note)
            self.slot_notes[channel][slot] = note
            self._light_slot(channel, slot, True)

    def _release(self, channel, note):
        self.link.note_off(channel, note)
        self.sounding[channel].discard(note)
        if channel in self.pitched:
            first = self.pitched[channel].pop(note, None)
            if first is not None:
                self._light(channel, first, self._pitch_section(channel, note)[1], False)
        elif channel in self.voices:
            slots = self.slot_notes[channel]
            for slot in range(len(slots)):
                if slots[slot] == note:
                    slots[slot] = None
                    self._light_slot(channel, slot, False)

    def _pick_slot(self, channel, note):
        slots = self.slot_notes[channel]
        if channel == ARP_CHANNEL:
            return self.arp.step_index % len(slots)
        for slot in range(len(slots)):
            if slots[slot] is None:
                return slot
        # All taken: share one rather than drop the light
        return note % len(slots)

    def _pitch_section(self, channel, note):
        """(first LED, LED count) of a pitched note's section."""
        _, zone_start, slots, slot_leds = self.voices[channel]
        zone_leds = slots * slot_leds
        count = zone_leds // PITCH_SECTION_FRACTION
        low, high = VOICE_PITCH_RANGES[channel]
        note = min(max(note, low), high)
        offset = (note - low) * (zone_leds - count) // max(high - low, 1)
        return zone_start + offset, count

    def _light_slot(self, channel, slot, on):
        _, zone_start, _, slot_leds = self.voices[channel]
        self._light(channel, zone_start + slot * slot_leds, slot_leds, on)

    def _light(self, channel, first, count, on):
        hue = self.voices[channel][0]
        strip = self.strip
        for i in range(first, first + count):
            if on:
                strip.set_hsv(i, hue, 1.0, BRIGHTNESS)
            else:
                strip.set_rgb(i, 0, 0, 0)
        self.strip_dirty = True
