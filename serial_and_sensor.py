# Test Serial Port send/receive
# To test, mpremote run serial.py

from machine import UART, Pin
import time

# Initialize UART 1 on pins GP20 (TX) and GP21 (RX).
# The RP2040/RP2350 chip allows multiple pin mappings for each UART peripheral.
# For UART1, one option is GP20 for TX and GP21 for RX.
uart1 = UART(1, baudrate=9600, tx=Pin(20), rx=Pin(21))
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1), bits=8, parity=None, stop=1)

print("Listening for data from Daisy Seed...")

# set up the Pico W's onboard LED
pico_led = Pin('LED', Pin.OUT)

presence = None
distance_cm = 50.0
last_presence = False
last_distance_cm = 1000.0
last_distance_ms = 0


def get_distance():
    """ generates a sin betwixt 0 and 10 if distance, the unit is meters """
    global last_presence, last_distance_cm, distance_cm, presence, last_distance_ms
    if uart.any():
        line = uart.readline()
        if not line:
            return
        #print("line is: ", line)

        try:
            text = line.decode('utf-8').strip()
        except UnicodeError:
            return

        if text.startswith("ON"):
            presence = True
        elif text.startswith("OFF"):
            presence = False
        elif text.startswith("Range"):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                distance_cm = int(parts[1])
                #print("Range: {} cm ({:.2f} m)".format(distance_cm, distance_cm / 100.0))


while True:
    get_distance()
    print("loop distance", distance_cm)
    #uart1.write(int(distance_cm).to_bytes(2, "little"))
    time.sleep(.5)