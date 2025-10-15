# Test Serial Port send/receive
# To test, mpremote run serial.py

from machine import UART, Pin
import time

# Initialize UART 1 on pins GP20 (TX) and GP21 (RX).
# The RP2040/RP2350 chip allows multiple pin mappings for each UART peripheral.
# For UART1, one option is GP20 for TX and GP21 for RX.
# uart = UART(1, baudrate=9600, tx=Pin(20), rx=Pin(21))
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

print("Listening for data from Daisy Seed...")

while True:
    if uart.any(): # Check if any data is available to read
        data = uart.read()
        if data:
            try:
                message = data.decode('utf-8').strip()
                print(f"Received: {message}")
            except UnicodeError:
                print("Received non-UTF-8 data.")

