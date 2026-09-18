import plasma 
import time
from machine import UART, Pin
from pimoroni import RGBLED


# Address of this node on RS-485
MY_ADDRESS = 1

# Number of LEDs on this node
NUM_LEDS = 1

# Set the LED brightness (1.0 max)
BRIGHTNESS = 0.5

# Illuminated time for LED in msec
FLASH_DURATION_MSEC = 200

# UART on Pimoroni Plasma 2350
# uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
uart = UART(1, baudrate=9600, tx=Pin(20), rx=Pin(21))

class Commands:
    FLASH = 0b010
    FADE = 0b100
    SEND_SENSOR = 0b001
    SET_COLOR = 0b011
    CLOCK = 0b111

class State:
    WAITING = 1
    FLASH = 2
    FADE = 3
    state = WAITING

    def isState(check_state):
        return State.state == check_state

# set up the Pico W's onboard LED
pico_led = RGBLED("LED_R", "LED_G", "LED_B")

# set up the WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)

# start updating the LED strip
led_strip.start()

# Starting Neopixel hue
hue = 30

# Other vars
flash_start = 0

print("Node started...")

time.sleep(0.4)

# Flash the onboard LED
for i in range(2):
    pico_led.set_rgb(255, 0, 0)
    led_strip.set_hsv(0, hue / 360, 1.0, BRIGHTNESS)
    time.sleep(0.2)
    pico_led.set_rgb(0, 0, 0)
    led_strip.set_hsv(0, 0, 0, 0)
    time.sleep(0.2)

# Flash Neopixel
State.state = State.FLASH
# led_strip.set_hsv(0, hue / 360, 1.0, BRIGHTNESS)
flash_start = time.ticks_ms()

while True:

    if uart.any():
        raw = uart.read(1)
        byte = raw[0]
        
        command = (byte & 0xe0) >> 5
        address = (byte & 0x1f)

        if address not in (MY_ADDRESS, 0):
            continue

        if command == Commands.FLASH:
            led_strip.set_hsv(0, hue / 360, 1.0, BRIGHTNESS)
            flash_start = time.ticks_ms()
            State.state = State.FLASH
            # print("Command ", command, "address ", address, "byte", hex(byte))

        elif command == Commands.SET_COLOR:
            hue = uart.read(2)
            led_strip.set_hsv(0, hue / 360, 1.0, BRIGHTNESS)
            # print("Command ", command, "address ", address, "byte", hex(byte))

        # elif command == Commands.CLOCK:
            # print("Clock ", command, "address ", address, "byte", hex(byte))

    if State.isState(State.FLASH):
        if flash_start + FLASH_DURATION_MSEC < time.ticks_ms():
            led_strip.set_hsv(0, 0, 0, 0)
            State.state = State.WAITING
        
    time.sleep(0.001)

