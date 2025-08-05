import time

from machine import Pin
import plasma
import time

pico_led = Pin("LED", Pin.OUT)

while True:
    pico_led.value(True)
    time.sleep(0.5)

    # Turn all LEDs off
    pico_led.value(False)
    time.sleep(0.5)

