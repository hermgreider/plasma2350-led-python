from machine import UART, Pin

"""
The RS-485 bus between portals. One controller transmits; every node only
listens and picks out the frames addressed to it.

Frame:
  [START][ADDR][TYPE][LEN][payload: LEN bytes][CRC8]
  START  0xA5
  ADDR   0 = broadcast (MIDI clock), 1-239 = a node, 240-254 reserved for
         groups, 255 reserved
  TYPE   TYPE_MIDI: payload is one or more complete MIDI messages, channels
         local to the addressed node. Other types are reserved -- e.g. MIDI
         stamped with the clock tick it should fire on, if notes ever need
         sending ahead.
  CRC8   polynomial 0x07 over ADDR, TYPE, LEN and the payload

A receiver that loses its place (noise, joining mid-frame) hunts for the
next START; the CRC throws out a false start.

Wiring (PortalPCB V2): MAX3485 RXD -> Plasma GP21 (UART1 RX), TXD <- GP20
(UART1 TX), EN on GP28 (high = transmit). The bus is one-way, so the
controller holds EN high and nodes hold it low, permanently -- no switching
direction per frame.
"""

START = 0xA5
BROADCAST = 0
TYPE_MIDI = 1
MAX_PAYLOAD = 32

BAUD = 115200

_UART_ID = 1
_TX_PIN = 20
_RX_PIN = 21
_EN_PIN = 28


def _crc8(data, crc=0):
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def airtime_us(payload_len):
    """How long a frame with this much payload takes on the wire: 10 bits
    per byte (start, 8 data, stop)."""
    return (payload_len + 5) * 10 * 1_000_000 // BAUD


class BusTransmitter:
    def __init__(self):
        self.uart = UART(_UART_ID, baudrate=BAUD, tx=Pin(_TX_PIN), rx=Pin(_RX_PIN), txbuf=1024)
        self.en = Pin(_EN_PIN, Pin.OUT, value=1)
        self.frames_sent = 0

    def send(self, address, payload, frame_type=TYPE_MIDI):
        header = bytes((address, frame_type, len(payload)))
        crc = _crc8(payload, _crc8(header))
        self.uart.write(bytes((START,)) + header + payload + bytes((crc,)))
        self.frames_sent += 1


class BusReceiver:
    def __init__(self, address):
        self.address = address
        self.uart = UART(_UART_ID, baudrate=BAUD, tx=Pin(_TX_PIN), rx=Pin(_RX_PIN), rxbuf=2048)
        self.en = Pin(_EN_PIN, Pin.OUT, value=0)

        self.frames = 0
        self.crc_errors = 0

        self._buf = bytearray()

    def drain(self):
        """Throws away anything received so far."""
        while self.uart.any():
            self.uart.read()
        self._buf = bytearray()

    def poll(self, handle):
        """Reads what's arrived and calls handle(frame_type, payload) for each
        complete frame addressed to this node or broadcast. Returns True if
        any frame (for anyone) completed."""
        if self.uart.any():
            self._buf.extend(self.uart.read())

        got_any = False
        buf = self._buf
        while True:
            # Hunt for START (bytearray.find isn't on every MicroPython build)
            start = 0
            while start < len(buf) and buf[start] != START:
                start += 1
            if start > 0:
                buf = buf[start:]
            if not buf:
                break

            if len(buf) < 4:
                break
            length = buf[3]
            if length > MAX_PAYLOAD:
                # Can't be a real header: skip this START
                buf = buf[1:]
                continue
            total = 4 + length + 1
            if len(buf) < total:
                break

            if _crc8(buf[1:4 + length]) != buf[4 + length]:
                self.crc_errors += 1
                buf = buf[1:]
                continue

            address = buf[1]
            frame_type = buf[2]
            payload = bytes(buf[4:4 + length])
            buf = buf[total:]
            self.frames += 1
            got_any = True

            if address == self.address or address == BROADCAST:
                handle(frame_type, payload)

        self._buf = buf
        return got_any
