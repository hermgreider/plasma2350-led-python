"""
An Up arpeggiator stepping on MIDI clock: a port of Portalv2's
source/arpeggiator.cpp (Up direction only), moved here so the Plasma knows
every note that sounds and its LEDs can follow each step.

Held notes are kept sorted by pitch and walked in order, one per step. The
first note held starts right away instead of waiting for the next step.
"""


class Arpeggiator:
    def __init__(self, play, release, ticks_per_step=6):
        """play(note, velocity) and release(note) are called to sound and
        stop each step. ticks_per_step is MIDI clock pulses per step: 24 per
        quarter note, so 6 is 1/16 notes."""
        self.play = play
        self.release = release
        self.ticks_per_step = ticks_per_step

        # [note, velocity] pairs, sorted by note
        self.held = []
        self.tick = 0
        self.step_index = -1
        self.playing_note = None

    def note_on(self, note, velocity):
        for pair in self.held:
            if pair[0] == note:
                pair[1] = velocity
                return

        insert = len(self.held)
        while insert > 0 and self.held[insert - 1][0] > note:
            insert -= 1
        self.held.insert(insert, [note, velocity])

        if len(self.held) == 1:
            self.tick = 0
            self._advance()

    def note_off(self, note):
        for i, pair in enumerate(self.held):
            if pair[0] == note:
                del self.held[i]
                # Keep pointing at the same logical note
                if self.step_index >= i:
                    self.step_index -= 1
                break

        if self.playing_note == note:
            self._release_current()

        if not self.held:
            self.step_index = -1

    def on_clock_tick(self):
        if not self.held:
            return

        self.tick += 1
        if self.tick >= self.ticks_per_step:
            self.tick = 0
            self._advance()

    def _advance(self):
        self._release_current()
        if not self.held:
            return

        count = len(self.held)
        if self.step_index >= count:
            self.step_index = count - 1
        self.step_index = (self.step_index + 1) % count

        note, velocity = self.held[self.step_index]
        self.play(note, velocity)
        self.playing_note = note

    def _release_current(self):
        if self.playing_note is not None:
            self.release(self.playing_note)
        self.playing_note = None
