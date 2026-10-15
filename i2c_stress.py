import time
from daisy_link import DaisyLink

"""
I2C link stress test: sends MIDI Note Offs to the Daisy back to back, as fast
as MicroPython can, then checks the Daisy counted every one.

The Note Offs go to channel 15, which no program uses, so nothing sounds.

Needs lib/daisy_link.py on the board (see that file), then:
  mpremote run i2c_stress.py
"""

COUNT = 2000
CHANNEL = 15

link = DaisyLink()

print("Connecting to the Daisy...")
while link.connect() is None:
    time.sleep_ms(500)
print("Connected")

# Let the Daisy's "connected" phrase finish
time.sleep_ms(1500)

before = link.packets_received()

start = time.ticks_us()
for i in range(COUNT):
    link.note_off(CHANNEL, i & 0x7F)
elapsed_us = time.ticks_diff(time.ticks_us(), start)

# Let the Daisy's main loop drain its queue
time.sleep_ms(50)
after = link.packets_received()
status = link.read_status()

counted = (after - before) & 0xFFFF
print("sent", COUNT, "in", elapsed_us // 1000, "ms,",
      elapsed_us // COUNT, "us each")
print("retries", link.retries, "failures", link.failures)
print("Daisy counted", counted, "dropped/errors", status[5] if status else "?")
print("PASS" if counted == COUNT and link.failures == 0 else "FAIL")
