import plasma 
import time
from machine import UART, Pin
from pimoroni import RGBLED, Button


# Address of this node on RS-485
MY_ADDRESS = 0 # HOST
NUM_NODES = 3  # Includes HOST

# Number of LEDs on this node
NUM_LEDS = 1

# Set the LED brightness (1.0 max)
BRIGHTNESS = 0.5

# Illuminated time for LED in msec
DURATION_MSEC = 200
INTERVAL_MSEC = 2000

# UART on Pimoroni Plasma 2350
# uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
uart = UART(1, baudrate=9600, tx=Pin(20), rx=Pin(21))

# Enable pin is A0
en_pin = Pin(26, Pin.OUT, value=0)

class Command:
    FLASH = 0b010
    FADE = 0b100
    SEND_SENSOR = 0b001
    SET_COLOR = 0b011
    CLOCK = 0b111

class State:
    WAITING = 1
    FLASH = 2

class Program:
    WAITING = 1
    FLASH = 2
    FADE = 3
    STEP = 4

class Color:
    RED = 0x600000
    BLUE = 0x00007f
    GREEN = 0x005000
    ALL = 0

class ProgramColor:
    program_colors = ( 
        (Program.FLASH, Color.RED), 
        (Program.FLASH, Color.BLUE), 
        (Program.FLASH, Color.GREEN), 
        (Program.FADE, Color.RED), 
        (Program.FADE, Color.BLUE), 
        (Program.STEP, Color.RED), 
        (Program.STEP, Color.GREEN), 
        (Program.STEP, Color.ALL) )

    current_program_color = 0

    def currentProgram():
        return (ProgramColor.program_colors[ProgramColor.current_program_color])[0]
    
    def currentColor():
        return (ProgramColor.program_colors[ProgramColor.current_program_color])[1]
    
    def nextProgramColor():
        ProgramColor.current_program_color = (ProgramColor.current_program_color + 1) % len(ProgramColor.program_colors)
        return ProgramColor.program_colors[ProgramColor.current_program_color]

class LedHelper:
    def set_rgb(index):
        hex_color = ProgramColor.currentColor()
        r = (hex_color >> 16) & 0xFF
        g = (hex_color >> 8) & 0xFF
        b = hex_color & 0xFF
        led_strip.set_rgb(index, r, g, b)

    def set_off(index):
        led_strip.set_rgb(index, 0, 0, 0)

# Onboard button on Plasma
button_a = Button("BUTTON_A")

# set up the Pico W's onboard LED
pico_led = RGBLED("LED_R", "LED_G", "LED_B")

# set up the WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)

# start updating the LED strip
led_strip.start()

# Other vars
program_start = 0

print("Host started...")

time.sleep(0.4)

# Flash the onboard LED
for i in range(2):
    pico_led.set_rgb(255, 0, 0)
    time.sleep(0.2)
    pico_led.set_rgb(0, 0, 0)

# Start first program
state = State.WAITING

program_start = time.ticks_ms() - 1000
next_clock = time.ticks_ms() 

while True:

    # Response - for now, do nothing. Handle responses later.
    if uart.any():
        byte = uart.read(1)
        print("received")

    # Send clock
    if time.ticks_diff(time.ticks_ms(), next_clock) >= 0:
        # Send clock
        en_pin.value(1)
        uart.write(b'\xE0')
        uart.flush()
        en_pin.value(0)

        # print("Sent clock")

        # Schedule the next clock 100ms from now
        next_clock = time.ticks_add(next_clock, 100)

    if button_a.read() == True:
        ProgramColor.nextProgramColor()
        
        # Send color to Addr 0
        # packet = bytes(Commands.SET_COLOR)
        # + bytes(*colors[color_index])
        # uart.write(packet[0])
        # uart.write(packet[1])
        # uart.write(packet[2])
        # uart.write(packet[3])

    if ProgramColor.currentProgram() == Program.FLASH:

        # Start the next flash program
        if time.ticks_diff(time.ticks_ms(), program_start + INTERVAL_MSEC) >= 0:
            
            # Send flash command to all nodes
            # print(hex(Command.FLASH << 5))
            # uart.write(bytes(Command.FLASH << 5))
            en_pin.value(1)
            uart.write(b'\x40')
            uart.flush()
            en_pin.value(0)
            
            # Turn on my own LED
            LedHelper.set_rgb(0)

            state = State.FLASH
            program_start = time.ticks_ms()

        # Turn off my own color
        if state == State.FLASH and (time.ticks_diff(time.ticks_ms(), program_start + DURATION_MSEC) >= 0):
            LedHelper.set_off(0)
            state = State.WAITING

