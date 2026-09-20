import time
from machine import I2C, Pin

"""
I2C host (controller) — sends a simple "ping" command to the Daisy Seed
(target) and prints whatever comes back.

Plasma 2350 wiring:
  SCL = pin 5 = A1 = GPIO27
  SDA = pin 6 = A0 = GPIO26
Both lines have external 4.7k pullups to 3.3V, so internal pulls are left off.

A0/A1 sit on I2C1's native pins, so this uses I2C bus 1.
"""

# Target (Daisy) 7-bit I2C address. Change this once the Daisy side picks one.
DAISY_ADDR = 0x42

# Command byte sent to the Daisy. Daisy code (written next) should recognize
# this and reply with something — anything — so we know the link works.
CMD_PING = 0x01

# How many bytes to try to read back after a ping
RESPONSE_LEN = 1

# How often to ping, in seconds
PING_INTERVAL = 1.0

i2c = I2C(1, scl=Pin(27), sda=Pin(26), freq=100_000)

print("I2C host started...")

while True:
    # Look for devices on the bus — useful for confirming the Daisy's
    # address once it's actually running I2C slave code.
    devices = i2c.scan()
    if devices:
        print("Devices found:", [hex(addr) for addr in devices])
    else:
        print("No devices found on the bus")

    # Send the ping command
    try:
        i2c.writeto(DAISY_ADDR, bytes([CMD_PING]))
        print("Sent ping to", hex(DAISY_ADDR))
    except OSError as e:
        print("Write failed (no ACK from", hex(DAISY_ADDR), "):", e)
        time.sleep(PING_INTERVAL)
        continue

    # Try to read a response
    try:
        response = i2c.readfrom(DAISY_ADDR, RESPONSE_LEN)
        print("Response:", response)
    except OSError as e:
        print("Read failed:", e)

    time.sleep(PING_INTERVAL)
