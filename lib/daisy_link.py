import os
import time
from machine import I2C, Pin

"""
The Plasma's end of the I2C link to the Daisy Seed on the same PortalPCB.
The Plasma is the controller; the Daisy is the target.

Every write starts with a packet-type byte:
  PACKET_CONNECT  [type, protocol version, token]
      Hello on startup. The Daisy echoes token in its status block, so a
      matching echo means *this* Connect landed, not a stale one from before
      the Plasma rebooted.
  PACKET_MIDI     [type, MIDI bytes...]
      Complete MIDI messages. Channels are local to this board.

A read returns the Daisy's status block:
  [STATUS_MAGIC, protocol version, last Connect token,
   packets received (low, high), dropped + errors (saturating at 255)]

Must match source/plasma_link.h in the Portalv2 (Daisy) project.

Wiring (PortalPCB V2):
  SCL = Plasma A1 = GPIO27  <->  Daisy D11
  SDA = Plasma A0 = GPIO26  <->  Daisy D12
4.7k pull-ups on the board. A0/A1 are I2C1's native pins.

Copy to the board with:
  mpremote fs mkdir lib
  mpremote fs cp lib/daisy_link.py :lib/daisy_link.py
"""

DAISY_ADDR = 0x42
PROTOCOL_VERSION = 1

PACKET_CONNECT = 0x01
PACKET_MIDI = 0x02

STATUS_MAGIC = 0xDA
STATUS_LEN = 6

# How many times to try a write before giving up on it. The Daisy stretches
# the clock rather than NACKing while it's busy, so retries should be rare --
# mostly while it's still booting.
WRITE_ATTEMPTS = 3


class DaisyLink:
    def __init__(self, freq=400_000):
        self.i2c = I2C(1, scl=Pin(27), sda=Pin(26), freq=freq)

        # Writes that failed once but went through on a retry, and writes
        # that never went through at all
        self.retries = 0
        self.failures = 0

        # Random start, so a Plasma reboot can't reuse the token the Daisy
        # is still showing from last time. Never 0, which is what the Daisy
        # boots with.
        self._token = os.urandom(1)[0] % 255 + 1

        # Preallocated so sending in the play loop never allocates
        self._msg1 = bytearray([PACKET_MIDI, 0])
        self._msg2 = bytearray([PACKET_MIDI, 0, 0])
        self._msg3 = bytearray([PACKET_MIDI, 0, 0, 0])
        self._status = bytearray(STATUS_LEN)

    def connect(self):
        """Says hello and waits for the Daisy to echo it.

        Returns True if the Daisy answered and speaks our protocol version,
        False if it answered with a different version, and None if it
        didn't answer at all (not booted yet, or not there).
        """
        self._token = self._token % 255 + 1
        try:
            self.i2c.writeto(DAISY_ADDR, bytes([PACKET_CONNECT, PROTOCOL_VERSION, self._token]))
        except OSError:
            return None

        # The Daisy handles the Connect from its main loop, not the
        # interrupt, so give it a moment before the echo shows up
        for _ in range(20):
            time.sleep_ms(5)
            status = self.read_status()
            if status is not None and status[2] == self._token:
                return status[1] == PROTOCOL_VERSION
        return None

    def read_status(self):
        """The Daisy's status block, or None if it didn't answer sensibly."""
        try:
            self.i2c.readfrom_into(DAISY_ADDR, self._status)
        except OSError:
            return None
        if self._status[0] != STATUS_MAGIC:
            return None
        return self._status

    def packets_received(self):
        """The Daisy's 16-bit count of packets it has received, or None."""
        status = self.read_status()
        if status is None:
            return None
        return status[3] | (status[4] << 8)

    def note_on(self, channel, note, velocity):
        self._msg3[1] = 0x90 | (channel & 0x0F)
        self._msg3[2] = note & 0x7F
        self._msg3[3] = velocity & 0x7F
        return self._write(self._msg3)

    def note_off(self, channel, note):
        self._msg3[1] = 0x80 | (channel & 0x0F)
        self._msg3[2] = note & 0x7F
        self._msg3[3] = 0
        return self._write(self._msg3)

    def program_change(self, channel, program):
        self._msg2[1] = 0xC0 | (channel & 0x0F)
        self._msg2[2] = program & 0x7F
        return self._write(self._msg2)

    def clock(self):
        """One MIDI clock pulse (24 per quarter note)."""
        self._msg1[1] = 0xF8
        return self._write(self._msg1)

    def _write(self, buf):
        for attempt in range(WRITE_ATTEMPTS):
            try:
                self.i2c.writeto(DAISY_ADDR, buf)
                if attempt > 0:
                    self.retries += 1
                return True
            except OSError:
                pass
        self.failures += 1
        return False
