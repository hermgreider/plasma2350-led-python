from machine import UART, Pin
import time

# UART0 on Pimoroni Plasma 2350
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1), bits=8, parity=None, stop=1)

print("HMMD mmWave Sensor (text mode) reader started...")

presence = None
distance_cm = 0.0
last_presence = False
last_distance_cm = 1000.0

while True:
    if uart.any():
        line = uart.readline()
        if not line:
            continue
        # print("line is: ", line)

        try:
            text = line.decode('utf-8').strip()
        except UnicodeError:
            continue

        if text.startswith("ON"):
            presence = True
        elif text.startswith("OFF"):
            presence = False
        elif text.startswith("Range"):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                distance_cm = int(parts[1])
                # print("Range: {} cm ({:.2f} m)".format(distance_cm, distance_cm / 100.0))

    if last_presence != presence:
        print("Presence: ", presence)
        last_presence = presence

    if last_distance_cm != distance_cm:
        print("Range: {} cm ({:.2f} m)".format(distance_cm, distance_cm / 100.0))
        last_distance_cm = distance_cm

    time.sleep(0.05)
