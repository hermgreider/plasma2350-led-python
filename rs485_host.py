import plasma
import time
from machine import UART, Pin
from pimoroni import RGBLED

# RS-485 test, host side. Run rs485_node.py on the other board.
#
# Every INTERVAL_MSEC the host sends FLASH to NODE_ADDRESS. The node flashes
# its LED and answers with ACK. The host flashes its onboard LED green when an
# ACK comes back, red if it times out, and prints a running count.
#
# Wiring: RJ45 patch cable (straight-through) from this board's J10 RS485_Out
# to the node's J4 RS485_In. Pins 4/5 carry B/A, pins 7/8 carry GND.

# Address of this node on RS-485
MY_ADDRESS = 0  # HOST
NODE_ADDRESS = 1

# Number of LEDs on this node
NUM_LEDS = 1

# Illuminated time for LED in msec
DURATION_MSEC = 200
INTERVAL_MSEC = 2000
REPLY_TIMEOUT_MSEC = 100

# PortalPCB V2: Plasma SDA/GP20 -> MAX3485 RXD, Plasma SCL/GP21 <- MAX3485 TXD
uart = UART(1, baudrate=9600, tx=Pin(20), rx=Pin(21))

# PortalPCB V2: MAX3485 EN is on Plasma A2 (GP28). High = transmit, low = receive.
# (A0/A1 are the I2C link to the Daisy, don't touch them here.)
en_pin = Pin(28, Pin.OUT, value=0)

class Command:
    FLASH = 0b010
    FADE = 0b100
    SEND_SENSOR = 0b001
    SET_COLOR = 0b011
    ACK = 0b110
    CLOCK = 0b111

def make_packet(command, address):
    return (command << 5) | (address & 0x1f)

def send(byte):
    en_pin.value(1)
    uart.write(bytes([byte]))
    uart.flush()
    # Wait for the stop bit to leave the shift register before releasing the bus
    while not uart.txdone():
        pass
    en_pin.value(0)

# set up the Plasma's onboard LED
pico_led = RGBLED("LED_R", "LED_G", "LED_B")

# set up the WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)

# start updating the LED strip
led_strip.start()

print("Host started...")

time.sleep(0.4)

# Flash the onboard LED
for i in range(2):
    pico_led.set_rgb(255, 0, 0)
    time.sleep(0.2)
    pico_led.set_rgb(0, 0, 0)
    time.sleep(0.2)

sent = 0
acked = 0
next_send = time.ticks_ms()
led_off_at = None

while True:

    if time.ticks_diff(time.ticks_ms(), next_send) >= 0:
        next_send = time.ticks_add(next_send, INTERVAL_MSEC)

        # Drop any stale bytes (e.g. noise from the node powering up)
        while uart.any():
            uart.read()

        send(make_packet(Command.FLASH, NODE_ADDRESS))
        sent += 1
        sent_at = time.ticks_ms()

        # Turn on my own LED
        led_strip.set_rgb(0, 0x60, 0, 0)

        # Wait for the node's ACK
        reply = None
        while time.ticks_diff(time.ticks_ms(), sent_at) < REPLY_TIMEOUT_MSEC:
            if uart.any():
                reply = uart.read(1)[0]
                break

        rtt = time.ticks_diff(time.ticks_ms(), sent_at)
        if reply == make_packet(Command.ACK, NODE_ADDRESS):
            acked += 1
            pico_led.set_rgb(0, 255, 0)
            print("ACK from node", NODE_ADDRESS, "in", rtt, "ms  (", acked, "/", sent, ")")
        elif reply is None:
            pico_led.set_rgb(255, 0, 0)
            print("No reply  (", acked, "/", sent, ")")
        else:
            pico_led.set_rgb(255, 0, 255)
            print("Unexpected byte", hex(reply), " (", acked, "/", sent, ")")

        led_off_at = time.ticks_add(time.ticks_ms(), DURATION_MSEC)

    # Turn off my own LEDs
    if led_off_at is not None and time.ticks_diff(time.ticks_ms(), led_off_at) >= 0:
        led_strip.set_rgb(0, 0, 0, 0)
        pico_led.set_rgb(0, 0, 0)
        led_off_at = None

    time.sleep(0.001)
