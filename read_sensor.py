from machine import Pin, time_pulse_us
import time

# Adjust to match the Plasma 2350 pin labels
TRIG_PIN = 27   # pick a GPIO wired to JSN-SR04T TRIG (through level shifter if needed)
ECHO_PIN = 28   # GPIO wired to JSN-SR04T ECHO (MUST be level-shifted to 3.3V)

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

def get_distance():
    # Ensure trigger is low
    trig.value(0)
    time.sleep_us(2)

    # Send 10 µs HIGH pulse to trigger
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    # Measure echo pulse width (timeout = 30 ms)
    try:
        duration = time_pulse_us(echo, 1, 30000)  # microseconds
    except OSError:  # timeout
        return None

    # Convert time to distance
    # Sound speed ~343 m/s → 29.1 µs per cm round-trip
    distance_cm = (duration / 2) / 29.1
    return distance_cm

while True:
    dist = get_distance()
    if dist is None:
        print("Out of range")
    else:
        print("Distance: {:.1f} cm".format(dist))
    time.sleep(1)
