import gc
import json
import time
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
      If the bus stays silent for NO_BUS_MSEC after startup, it plays the
      drone_lead song on its own until the bus wakes up. voices lists the
      MIDI channels this node plays; the strip is split evenly among them
      (default: all three, see node.py).

  {"address": 1, "controller": true, "song": "drone_lead_split", "voices": [1]}
      The controller, and also a node itself. Plays the song (see song.py,
      which says which node plays which part), sending each event to its
      node, and MIDI clock and Start to every node. Its own node's share is
      held back by at least a frame's wire time, and until frames already
      queued for the other nodes have left (see LOCAL_EXTRA_DELAY_US), so
      it doesn't play ahead of them.

Onboard LED: red while waiting for the Daisy, green once it answers,
magenta if it answers with a different protocol version.

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
DEFAULT_CONFIG = {"address": 1, "controller": False, "song": "drone_lead", "voices": [1, 0, 2]}

# A node with no bus traffic this long after startup plays its own demo
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


def load_config():
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE) as f:
            config.update(json.load(f))
    except OSError:
        print("No", CONFIG_FILE, "- using", DEFAULT_CONFIG)
    return config


def connect_daisy(link, led):
    print("Connecting to the Daisy...")
    while True:
        result = link.connect()
        if result is True:
            led.set_rgb(0, 255, 0)
            print("Connected")
            return
        if result is False:
            led.set_rgb(255, 0, 255)
            print("Daisy speaks a different protocol version -- playing anyway")
            return
        led.set_rgb(255, 0, 0)
        time.sleep_ms(500)


class Loop:
    """What every main loop shares: timing stats and quiet-time GC."""

    def __init__(self, node, link):
        self.node = node
        self.link = link
        self.light = Timing()
        self.gap = Timing()
        self.gc = Timing()
        now = time.ticks_ms()
        self.last_pass = time.ticks_us()
        self.last_activity = now
        self.last_gc = now
        self.next_stats = time.ticks_add(now, STATS_INTERVAL_MSEC)

    def start_pass(self):
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


def run_controller(config, node, link):
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
    loop = Loop(node, link)
    print("Controller: song", config["song"])

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


def run_node(config, node, link):
    bus = rs485_bus.BusReceiver(config["address"])
    bus.drain()

    # The fallback demo, while the bus is silent: [Player or None]
    fallback = [None]
    heard_bus = [False]
    started = time.ticks_ms()

    def on_frame(frame_type, payload):
        if fallback[0] is not None:
            print("Bus is live - stopping the demo")
            fallback[0] = None
            node.all_off()
        if frame_type == rs485_bus.TYPE_MIDI:
            node.handle(payload)

    loop = Loop(node, link)
    print("Node", config["address"], "listening")

    def stats():
        return "frames {} crc errors {}".format(bus.frames, bus.crc_errors)

    while True:
        pass_start = loop.start_pass()
        active = bus.poll(on_frame)
        if active:
            heard_bus[0] = True

        if (not heard_bus[0] and fallback[0] is None
                and time.ticks_diff(time.ticks_ms(), started) >= NO_BUS_MSEC):
            print("No bus traffic - playing", FALLBACK_SONG)
            song, tempo = SONGS[FALLBACK_SONG]
            fallback[0] = Player(song, tempo, lambda address, payload: node.handle(payload))

        if fallback[0] is not None and fallback[0].tick():
            active = True

        loop.end_pass(pass_start, active, stats)


config = load_config()
print("Config:", config)

led = RGBLED("LED_R", "LED_G", "LED_B")
link = DaisyLink()

# No start(): the node pushes the strip out by hand, right after each change
strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)
strip.clear()
strip.update()

node = Node(link, strip, config["voices"])

connect_daisy(link, led)
time.sleep_ms(AFTER_CONNECT_MSEC)

if config.get("controller"):
    run_controller(config, node, link)
else:
    run_node(config, node, link)
