Aaron Notes - I have already done the first two for you

Connect LED strip

1. Disconnect Plasma from power!
2. 3 wires - red/black/white - 5V, ground, data
3. Wired 5V, Ground, and Data to Plasma (CLK is unused)

Setup MicroPython

1. Hit Boot, then Reset. RP2350 filesystem appeared.
2. Downloaded plasma_2350_w-test-004-micropython-with-filesystem.uf2 from https://github.com/pimoroni/plasma/releases/
3. Dropped uf2 file onto RP2350 filesystem

On Mac, Install mpremote to communicate with MicroPython

	python3 -m pip install --upgrade mpremote
	export PATH=/Users/hermgreider/Library/Python/3.9/bin:$PATH
	mpremote connect auto repl

Commands

	mpremote fs cp main.py
	mpremote fs ls
	mpremote fs rm main.py
	mpremote run blink.py # run a local file

MicroPython

	File started on boot is named main.py

Test with onboard LED

	Wrote a quick blink.py - worked
	Tried plasma2040/rgb-led-and-buttons.py - worked

