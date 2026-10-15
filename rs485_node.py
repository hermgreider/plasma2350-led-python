import plasma
import time
from machine import UART, Pin
from pimoroni import RGBLED

# RS-485 test, node side. Run rs485_host.py on the other board.
#
# Flashes the LED on FLASH, and answers FLASH sent to MY_ADDRESS with ACK.
# The onboard LED blinks blue on every byte received, even ones for other
# addresses, so you can tell the bus is alive without an LED strip.

# Address of this node on RS-485
MY_ADDRESS = 1

# Number of LEDs on this node
NUM_LEDS = 1

# Set the LED brightness (1.0 max)
BRIGHTNESS = 0.5

# Illuminated time for LED in msec
FLASH_DURATION_MSEC = 200

# Give the host time to switch its transceiver back to receive before replying
REPLY_DELAY_MSEC = 2

# PortalPCB V2: Plasma SDA/GP20 -> MAX3485 RXD, Plasma SCL/GP21 <- MAX3485 TXD
uart = UART(1, baudrate=9600, tx=Pin(20), rx=Pin(21))

# PortalPCB V2: MAX3485 EN is on Plasma A2 (GP28). High = transmit, low = receive.
# The board has no pull-down on EN, so drive it low right away or this node
# can sit in transmit mode and jam the bus.
en_pin = Pin(28, Pin.OUT, value=0)

class Commands:
    FLASH = 0b010
    FADE = 0b100
    SEND_SENSOR = 0b001
    SET_COLOR = 0b011
    ACK = 0b110
    CLOCK = 0b111

class State:
    WAITING = 1
    FLASH = 2
    FADE = 3
    state = WAITING

    def isState(check_state):
        return State.state == check_state

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

# Starting Neopixel hue
hue = 30

# Other vars
flash_start = 0

print("Node", MY_ADDRESS, "started...")

time.sleep(0.4)

# Flash the onboard LED
for i in range(2):
    pico_led.set_rgb(255, 0, 0)
    led_strip.set_hsv(0, hue / 360, 1.0, BRIGHTNESS)
    time.sleep(0.2)
    pico_led.set_rgb(0, 0, 0)
    led_strip.set_hsv(0, 0, 0, 0)
    time.sleep(0.2)

# Drop anything that arrived during startup
while uart.any():
    uart.read()

while True:

    if uart.any():
        byte = uart.read(1)[0]

        command = (byte & 0xe0) >> 5
        address = (byte & 0x1f)

        pico_led.set_rgb(0, 0, 255)
        flash_start = time.ticks_ms()
        State.state = State.FLASH

        if address in (MY_ADDRESS, 0):

            if command == Commands.FLASH:
                led_strip.set_hsv(0, hue / 360, 1.0, BRIGHTNESS)
                print("FLASH, address", address)

                # Only answer when addressed directly, so broadcasts don't collide
                if address == MY_ADDRESS:
                    time.sleep_ms(REPLY_DELAY_MSEC)
                    send(make_packet(Commands.ACK, MY_ADDRESS))

            elif command == Commands.SET_COLOR:
                # Hue follows as 2 bytes, big-endian, 0-359
                data = uart.read(2)
                if data is not None and len(data) == 2:
                    hue = ((data[0] << 8) | data[1]) % 360
                    led_strip.set_hsv(0, hue / 360, 1.0, BRIGHTNESS)

            elif command != Commands.CLOCK:
                print("Command", command, "address", address, "byte", hex(byte))

    if State.isState(State.FLASH):
        if time.ticks_diff(time.ticks_ms(), flash_start) >= FLASH_DURATION_MSEC:
            led_strip.set_hsv(0, 0, 0, 0)
            pico_led.set_rgb(0, 0, 0)
            State.state = State.WAITING

    time.sleep(0.001)
