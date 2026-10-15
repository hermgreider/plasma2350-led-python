"""
Songs the controller (or a node's fallback demo) can play.

A script is a tuple of (time ms, kind, channel, data1, data2) events, in time
order. route() turns it into a playable song by deciding which node plays
each channel: its events become (time ms, address, kind, channel, data1,
data2). Address 0 means every node. Channels are local to each node.
"""

NOTE_ON = 0
NOTE_OFF = 1
PROGRAM = 2

# A port of Portalv2's kDroneLeadScript, selecting the Daisy's program #12
# (#11 without the Daisy's own arpeggiator -- each node runs the arpeggio on
# channel 1 itself, from the shared clock)
DRONE_LEAD = (
    (0, PROGRAM, 0, 12, 0),

    # Short test note, then 5s of silence
    (200, NOTE_ON, 0, 60, 100),
    (500, NOTE_OFF, 0, 60, 0),

    (5500, NOTE_ON, 0, 48, 90),
    (5500, NOTE_ON, 0, 68, 80),

    (8000, NOTE_OFF, 0, 48, 0),
    (9500, NOTE_ON, 0, 55, 80),

    (12500, NOTE_OFF, 0, 68, 0),
    (14000, NOTE_ON, 0, 63, 80),

    (14000, NOTE_ON, 1, 60, 60),
    (14000, NOTE_ON, 1, 67, 60),
    (14000, NOTE_ON, 1, 75, 60),
    (14000, NOTE_ON, 1, 80, 60),

    (17000, NOTE_OFF, 0, 55, 0),
    (18200, NOTE_ON, 2, 67, 120),
    (18500, NOTE_ON, 0, 48, 80),

    (18700, NOTE_OFF, 2, 67, 0),
    (19500, NOTE_ON, 2, 78, 115),
    (19800, NOTE_OFF, 2, 78, 0),
    (20500, NOTE_ON, 2, 80, 110),
    (20700, NOTE_OFF, 2, 80, 0),
    (21000, NOTE_ON, 2, 78, 115),
    (21200, NOTE_OFF, 2, 78, 0),

    (21500, NOTE_OFF, 0, 63, 0),
    (23000, NOTE_ON, 0, 68, 80),

    (23500, NOTE_OFF, 1, 80, 0),
    (23500, NOTE_ON, 1, 63, 60),

    (24000, NOTE_ON, 2, 80, 50),
    (24500, NOTE_OFF, 2, 80, 0),
    (25500, NOTE_ON, 2, 68, 50),
    (26000, NOTE_OFF, 2, 68, 0),

    (26000, NOTE_OFF, 0, 48, 0),
    (27500, NOTE_ON, 0, 55, 80),

    (30500, NOTE_OFF, 0, 68, 0),
    (32000, NOTE_ON, 0, 63, 80),

    (33500, NOTE_OFF, 0, 55, 0),
    (35000, NOTE_ON, 0, 48, 80),

    (36500, NOTE_OFF, 0, 63, 0),
)


def _click():
    # One short, high Pluck (program #3) on every beat at 60 BPM, alternating
    # two pitches so a skipped beat is easy to spot. Sharp attacks and clean
    # gaps make start times easy to compare between boards.
    events = [(0, PROGRAM, 0, 3, 0)]
    for beat in range(8):
        t = 500 + beat * 1000
        note = 84 if beat % 2 == 0 else 79
        events.append((t, NOTE_ON, 0, note, 120))
        events.append((t + 80, NOTE_OFF, 0, note, 0))
    return tuple(events)


CLICK = _click()


def route(script, routes):
    """routes maps channel -> tuple of node addresses that play it (0 = every
    node). Program changes go to every address in routes, since each Daisy
    needs the program even if it plays only some of its channels. Events on
    channels not in routes are dropped."""
    everyone = []
    for addresses in routes.values():
        for address in addresses:
            if address not in everyone:
                everyone.append(address)

    song = []
    for time_ms, kind, channel, data1, data2 in script:
        addresses = everyone if kind == PROGRAM else routes.get(channel, ())
        for address in addresses:
            song.append((time_ms, address, kind, channel, data1, data2))
    return tuple(song)


EVERY_NODE = (0,)

# name -> (song, tempo in BPM for the clock)
SONGS = {
    # Every node plays every part
    "drone_lead": (route(DRONE_LEAD, {0: EVERY_NODE, 1: EVERY_NODE, 2: EVERY_NODE}), 60),

    # Node 1 plays the arpeggio; node 2 the drone and flute
    "drone_lead_split": (route(DRONE_LEAD, {1: (1,), 0: (2,), 2: (2,)}), 60),

    "click": (route(CLICK, {0: EVERY_NODE}), 60),
}
