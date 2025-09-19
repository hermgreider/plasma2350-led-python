import machine
import time

# A1 on Plasma 2350 = GPIO27
pin = machine.Pin(27, machine.Pin.OUT)
# You can use PULL_UP instead if your circuit expects the opposite

while True:
    pin.value(1)         # Set high
    time.sleep(3)        # Wait 3 seconds
    pin.value(0)         # Set low
    time.sleep(3)        # Wait 3 seconds