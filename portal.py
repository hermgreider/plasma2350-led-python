import gc
import json
import os
import sys
import time
import machine
import plasma
from pimoroni import RGBLED
from daisy_link import DaisyLink
from node import Node, NUM_LEDS
from player import Player
from song import SONGS
import rs485_bus

"""
A portal: the same code on every board, installed as main.py. node.json on
the board says which part it plays:

  {"address": 2, "voices": [0, 2]}
      A node. Listens on the RS-485 bus for frames addressed to it (and
      broadcasts), and plays them: sound on the Daisy, light on the strip.
      Whenever the bus goes silent for NO_BUS_MSEC (at startup, or because
      the controller went away mid-song), it lets go of everything and plays
      the drone_lead song on its own until the bus wakes up. voices lists the
      MIDI channels this node plays; the strip is split evenly among them
      (default: all three, see node.py).

  {"address": 1, "controller": true, "song": "drone_lead_split", "voices": [1]}
      The controller, and also a node itself. Plays the song (see song.py,
      which says which node plays which part), sending each event to its
      node, and MIDI clock and Start to every node. Its own node's share is
      held back by at least a frame's wire time, and until frames already
      queued for the other nodes have left (see LOCAL_EXTRA_DELAY_US), so
      it doesn't play ahead of them.

Onboard LED (see Status):
  red      waiting for the Daisy
  green    playing: following the bus, or the controller playing its song
  blue     playing its own demo, because the bus is silent
  magenta  the Daisy speaks a different protocol version (playing anyway)
  3 quick red flashes at startup: the last run crashed or hung, and the
           board reset itself -- details in crash.log on the board

Crashes and hangs: any unexpected exception is written to crash.log and
the board resets. A timer also checks the main loop is still going, and
resets the board if it's been stuck for HANG_MSEC. It's a software timer
rather than the RP2350's hardware watchdog because that one can't be
stopped once started: interrupting the board with mpremote to copy files
would get it reset mid-copy. Interrupting stops this one cleanly.

Every STATS_INTERVAL_MSEC it prints, avg/max in ms over the interval:
  late   (controller) a song event or clock tick went out after it was due
  light  from noticing MIDI to the strip push starting
  gap    between main-loop passes -- the worst-case wait for anything
  gc     the gc.collect() run when the loop is quiet

Copy to the board with:
  mpremote fs cp lib/*.py :lib/
  mpremote fs cp portal.py :main.py
  mpremote fs cp <that board's node.json> :node.json
"""

CONFIG_FILE = "node.json"
CRASH_LOG = "crash.log"
CRASH_FLAG = "crashed"

# Keep crash.log from filling the flash
CRASH_LOG_MAX_BYTES = 8192

# Reset the board if the main loop hasn't come round in this long
HANG_MSEC = 5000
DEFAULT_CONFIG = {"address": 1, "controller": False, "song": "drone_lead", "voices": [1, 0, 2]}

# A node with no bus traffic this long plays its own demo. The controller
# sends clock 24 times a beat, so a few seconds of silence means it's gone.
NO_BUS_MSEC = 4000
FALLBACK_SONG = "drone_lead"

# Let the Daisy's "connected" phrase finish before playing anything
AFTER_CONNECT_MSEC = 1500

STATS_INTERVAL_MSEC = 10_000

# Collect garbage once the loop has been quiet this long, at most this
# often, so a collection rarely lands between a note and its light
GC_IDLE_MSEC = 5
GC_INTERVAL_MSEC = 100

# On top of the frames' wire time, how much longer the controller holds back
# its own node's copy -- to match how long a remote node takes to notice and
# parse a frame. 0 until measured.
LOCAL_EXTRA_DELAY_US = 0


class Timing:
    """avg/max of a set of samples, in microseconds."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.total = 0
        self.count = 0
        self.max = 0

    def add(self, us):
        self.total += us
        self.count += 1
        if us > self.max:
            self.max = us

    def report(self, name):
        avg = self.total / self.count / 1000 if self.count else 0
        return "{} {:.1f}/{:.1f}".format(name, avg, self.max / 1000)


class Status:
    """The onboard RGB LED, showing what the portal is doing."""

    WAITING = (255, 0, 0)
    PLAYING = (0, 255, 0)
    DEMO = (0, 0, 255)
    MISMATCH = (255, 0, 255)

    def __init__(self):
        self.led = RGBLED("LED_R", "LED_G", "LED_B")
        self.mismatch = False

    def show(self, color):
        # A protocol mismatch outranks everything but waiting for the Daisy
        if self.mismatch and color != Status.WAITING:
            color = Status.MISMATCH
        self.led.set_rgb(*color)

    def flash_crashed(self):
        for _ in range(3):
            self.led.set_rgb(255, 0, 0)
            time.sleep_ms(150)
            self.led.set_rgb(0, 0, 0)
            time.sleep_ms(150)


class Watchdog:
    """Resets the board if feed() hasn't been called for HANG_MSEC. Checked
    from a timer, so it fires even if the main loop is stuck in Python."""

    def __init__(self):
        self.last_fed = time.ticks_ms()
        self.timer = machine.Timer(period=1000, callback=self._check)

    def feed(self):
        self.last_fed = time.ticks_ms()

    def stop(self):
        self.timer.deinit()

    def _check(self, _timer):
        if time.ticks_diff(time.ticks_ms(), self.last_fed) > HANG_MSEC:
            self.timer.deinit()
            record_crash("Main loop stuck for over {}ms".format(HANG_MSEC))
            machine.reset()


def record_crash(reason):
    """Appends reason (a message or an exception) to crash.log and leaves a
    flag for the next startup to show."""
    try:
        try:
            if os.stat(CRASH_LOG)[6] > CRASH_LOG_MAX_BYTES:
                os.remove(CRASH_LOG)
        except OSError:
            pass
        with open(CRASH_LOG, "a") as f:
            f.write("---- uptime {}s\n".format(time.ticks_ms() // 1000))
            if isinstance(reason, BaseException):
                sys.print_exception(reason, f)
            else:
                f.write(reason + "\n")
        with open(CRASH_FLAG, "w") as f:
            f.write("1")
    except OSError:
        # Never let logging the crash stop the reset
        pass


def crashed_last_time():
    try:
        os.remove(CRASH_FLAG)
        return True
    except OSError:
        return False


def load_config():
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE) as f:
            config.update(json.load(f))
    except OSError:
        print("No", CONFIG_FILE, "- using", DEFAULT_CONFIG)
    return config


def connect_daisy(link, status, watchdog):
    print("Connecting to the Daisy...")
    status.show(Status.WAITING)
    while True:
        watchdog.feed()
        result = link.connect()
        if result is True:
            print("Connected")
            return
        if result is False:
            status.mismatch = True
            print("Daisy speaks a different protocol version -- playing anyway")
            return
        time.sleep_ms(500)


class Loop:
    """What every main loop shares: timing stats and quiet-time GC."""

    def __init__(self, node, link, watchdog):
        self.node = node
        self.link = link
        self.watchdog = watchdog
        self.light = Timing()
        self.gap = Timing()
        self.gc = Timing()
        now = time.ticks_ms()
        self.last_pass = time.ticks_us()
        self.last_activity = now
        self.last_gc = now
        self.next_stats = time.ticks_add(now, STATS_INTERVAL_MSEC)

    def start_pass(self):
        self.watchdog.feed()
        pass_start = time.ticks_us()
        self.gap.add(time.ticks_diff(pass_start, self.last_pass))
        self.last_pass = pass_start
        return pass_start

    def end_pass(self, pass_start, active, extra_stats):
        if self.node.push_leds():
            self.light.add(time.ticks_diff(time.ticks_us(), pass_start))

        now = time.ticks_ms()
        if active:
            self.last_activity = now
        elif (time.ticks_diff(now, self.last_activity) >= GC_IDLE_MSEC
              and time.ticks_diff(now, self.last_gc) >= GC_INTERVAL_MSEC):
            gc_start = time.ticks_us()
            gc.collect()
            self.gc.add(time.ticks_diff(time.ticks_us(), gc_start))
            self.last_gc = now

        if time.ticks_diff(now, self.next_stats) >= 0:
            self.next_stats = time.ticks_add(self.next_stats, STATS_INTERVAL_MSEC)
            print(extra_stats(), self.light.report("light"), self.gap.report("gap"),
                  self.gc.report("gc"), "| daisy retries", self.link.retries,
                  "failures", self.link.failures)
            for t in (self.light, self.gap, self.gc):
                t.reset()
            # Don't count the print against the next gap
            self.last_pass = time.ticks_us()


def run_controller(config, node, link, status, watchdog):
    address = config["address"]
    song, tempo = SONGS[config["song"]]

    bus = rs485_bus.BusTransmitter()

    # Messages for this board's own node, held back until due: [due_us, payload]
    local_queue = []

    # When the transmitter will have finished everything queued so far
    tx_free_at = [time.ticks_us()]

    def emit(target, payload):
        now = time.ticks_us()
        if time.ticks_diff(tx_free_at[0], now) < 0:
            tx_free_at[0] = now

        if target != address:
            bus.send(target, payload)
            tx_free_at[0] = time.ticks_add(tx_free_at[0], rs485_bus.airtime_us(len(payload)))

        if target == address or target == rs485_bus.BROADCAST:
            # A remote node can't act before a whole frame has arrived
            due = time.ticks_add(now, rs485_bus.airtime_us(len(payload)))
            if time.ticks_diff(tx_free_at[0], due) > 0:
                due = tx_free_at[0]
            local_queue.append([time.ticks_add(due, LOCAL_EXTRA_DELAY_US), payload])

    player = Player(song, tempo, emit)
    loop = Loop(node, link, watchdog)
    print("Controller: song", config["song"])
    status.show(Status.PLAYING)

    def stats():
        avg, worst = player.take_late()
        return "late {:.1f}/{:.1f} frames {}".format(avg, worst, bus.frames_sent)

    while True:
        pass_start = loop.start_pass()
        active = player.tick()

        while local_queue and time.ticks_diff(time.ticks_us(), local_queue[0][0]) >= 0:
            node.handle(local_queue.pop(0)[1])
            active = True

        loop.end_pass(pass_start, active, stats)


def run_node(config, node, link, status, watchdog):
    bus = rs485_bus.BusReceiver(config["address"])
    bus.drain()

    # The fallback demo, while the bus is silent: [Player or None]
    fallback = [None]

    # When a frame (for anyone) last arrived; startup counts as one
    last_heard = [time.ticks_ms()]
    heard_any = [False]

    def on_frame(frame_type, payload):
        if fallback[0] is not None:
            print("Bus is live - stopping the demo")
            fallback[0] = None
            node.all_off()
            status.show(Status.PLAYING)
        if frame_type == rs485_bus.TYPE_MIDI:
            node.handle(payload)

    loop = Loop(node, link, watchdog)
    print("Node", config["address"], "listening")
    status.show(Status.PLAYING)

    def stats():
        return "frames {} crc errors {}".format(bus.frames, bus.crc_errors)

    while True:
        pass_start = loop.start_pass()
        active = bus.poll(on_frame)
        now = time.ticks_ms()
        if active:
            last_heard[0] = now
            heard_any[0] = True

        if fallback[0] is None and time.ticks_diff(now, last_heard[0]) >= NO_BUS_MSEC:
            print("Bus lost" if heard_any[0] else "No bus traffic", "- playing", FALLBACK_SONG)
            # Let go of anything the controller left sounding
            node.all_off()
            song, tempo = SONGS[FALLBACK_SONG]
            fallback[0] = Player(song, tempo, lambda address, payload: node.handle(payload))
            status.show(Status.DEMO)

        if fallback[0] is not None and fallback[0].tick():
            active = True

        loop.end_pass(pass_start, active, stats)


def main(status, watchdog):
    config = load_config()
    print("Config:", config)

    link = DaisyLink()

    # No start(): the node pushes the strip out by hand, right after each change
    strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)
    strip.clear()
    strip.update()

    node = Node(link, strip, config["voices"])

    connect_daisy(link, status, watchdog)
    time.sleep_ms(AFTER_CONNECT_MSEC)

    if config.get("controller"):
        run_controller(config, node, link, status, watchdog)
    else:
        run_node(config, node, link, status, watchdog)


status = Status()
if crashed_last_time():
    print("Restarted after a crash or hang - see", CRASH_LOG)
    status.flash_crashed()

watchdog = Watchdog()
try:
    main(status, watchdog)
except KeyboardInterrupt:
    # mpremote (or Ctrl-C) taking over: stop cleanly, don't reset
    watchdog.stop()
    raise
except Exception as e:
    watchdog.stop()
    sys.print_exception(e)
    record_crash(e)
    machine.reset()
