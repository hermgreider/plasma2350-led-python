from random import uniform
import math
import plasma
import time
import machine

# SONIC-NOISE.PY

TRIG = machine.Pin(27, machine.Pin.OUT)   
ECHO = machine.Pin(28, machine.Pin.IN)  # (with voltage divider)
last_distance = 45.0

def get_distance1():
    # send trigger pulse
    TRIG.low()
    time.sleep_us(2)
    TRIG.high()
    time.sleep_us(10)
    TRIG.low()
    
    # Measure echo pulse width (timeout = 30 ms)
    try:
        duration = machine.time_pulse_us(ECHO, 1, 30000)  # microseconds
    except OSError:  # timeout
        return None

    # Convert time to distance
    # Sound speed ~343 m/s → 29.1 µs per cm round-trip
    distance_cm = (duration / 2) / 29.1
    return distance_cm


def get_distance():
    global last_distance
    # Ensure trigger is low
    TRIG.value(0)
    time.sleep_us(2)

    # Send 10 µs HIGH pulse to trigger
    TRIG.value(1)
    time.sleep_us(10)
    TRIG.value(0)

    # Measure echo pulse width (timeout = 30 ms)
    try:
        duration = machine.time_pulse_us(ECHO, 1, 30000)  # microseconds
    except OSError:  # timeout
        return None

    # Convert time to distance
    # Sound speed ~343 m/s → 29.1 µs per cm round-trip
    distance_cm = (duration / 2) / 29.1

    if distance_cm < 22.7:
        distance_cm = last_distance
    last_distance = distance_cm
    return distance_cm

# ----------------------------
# CONFIG
# THIS IS THE MOST RECENT ONE
# ----------------------------
NUM_LEDS = 120
SPARKLE_PROBABILITY = .005
FADE_UP_SPEED = 4
FADE_DOWN_SPEED = 4
brightness = .5  # 0.0 to 1.0
brightness_array = [uniform(.25, 1) for _ in range(NUM_LEDS)]
noise_speed = 0.05  # lower = slower animation
NOISE_Y_OFFSET = 0.3

# Color palette: list of RGB tuples (0–255)
PALETTE = [
    (0, 255, 0),     # Red
    (10, 255, 0),   # Orange
    (50, 80, 0),   # Yellow
    (80, 255, 0),     # Green
    (255, 255, 20),     # Blue
    (255, 255, 255),   # Purple
]

# ----------------------------
# BEZIER + NOISE FUNCTIONS
# ----------------------------
def quad_bezier_point(p0, p1, p2, t):
    u = 1 - t
    return (
        u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0],
        u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]
    )

def approx_bezier_length(p0, p1, p2, steps=20):
    length = 0
    prev = quad_bezier_point(p0, p1, p2, 0)
    for i in range(1, steps+1):
        t = i / steps
        curr = quad_bezier_point(p0, p1, p2, t)
        dx = curr[0] - prev[0]
        dy = curr[1] - prev[1]
        length += (dx*dx + dy*dy) ** 0.5
        prev = curr
    return length

def stitch_quadratic_beziers(curves, num_points, steps_per_curve=100):
    lengths = []
    total_length = 0
    for p0, p1, p2 in curves:
        seg_len = approx_bezier_length(p0, p1, p2, steps=steps_per_curve)
        lengths.append(seg_len)
        total_length += seg_len

    spacing = total_length / (num_points - 1)
    points = []
    seg_index = 0
    dist_in_seg = 0
    p0, p1, p2 = curves[0]
    prev_point = quad_bezier_point(p0, p1, p2, 0)
    points.append(prev_point)
    t_index = 0

    while len(points) < num_points and seg_index < len(curves):
        p0, p1, p2 = curves[seg_index]
        while t_index < steps_per_curve:
            t_index += 1
            t = t_index / steps_per_curve
            curr_point = quad_bezier_point(p0, p1, p2, t)
            dx = curr_point[0] - prev_point[0]
            dy = curr_point[1] - prev_point[1]
            step_len = (dx*dx + dy*dy) ** 0.5
            dist_in_seg += step_len
            if dist_in_seg >= spacing:
                points.append(curr_point)
                dist_in_seg = 0
                prev_point = curr_point
                if len(points) >= num_points:
                    break
            else:
                prev_point = curr_point
        seg_index += 1
        t_index = 0
        dist_in_seg = 0
        if seg_index < len(curves):
            prev_point = quad_bezier_point(*curves[seg_index], 0)

    while len(points) < num_points:
        points.append(points[-1])
    return points

def random2(x, y):
    dot = x * 12.9898 + y * 78.233
    return (math.sin(dot) * 43758.5453123) % 1.0

def noise2(x, y):
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy

    a = random2(ix, iy)
    b = random2(ix + 1.0, iy)
    c = random2(ix, iy + 1.0)
    d = random2(ix + 1.0, iy + 1.0)

    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)

    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy

def color_from_palette(t, led_brightness):
    #led_brightness = led_brightness * uniform(0, 1)
    """t: 0.0–1.0 → returns RGB from PALETTE with blending"""
    t = max(0.0, min(0.9999, t)) * (len(PALETTE) - 1)
    i = int(t)
    frac = t - i
    r1, g1, b1 = PALETTE[i]
    r2, g2, b2 = PALETTE[(i + 1) % len(PALETTE)]
    #if SPARKLE_PROBABILITY < uniform(0, 1):
    return (
        int((r1 + (r2 - r1) * frac) * led_brightness),
        int((g1 + (g2 - g1) * frac) * led_brightness),
        int((b1 + (b2 - b1) * frac) * led_brightness)
    )
    #else:
    #    return (
    #        int(25),
    #        int(25),
    #        int(25)
    #    )


def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1, c2, t):
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )

def display_current():
    for i in range(NUM_LEDS):
        r, g, b = current_leds[i]
        led_strip.set_rgb(i, r, g, b)

def move_to_target():
    for i in range(NUM_LEDS):
        for c in range(3):
            if current_leds[i][c] < target_leds[i][c]:
                current_leds[i][c] = min(current_leds[i][c] + FADE_UP_SPEED, target_leds[i][c])
            elif current_leds[i][c] > target_leds[i][c]:
                current_leds[i][c] = max(current_leds[i][c] - FADE_DOWN_SPEED, target_leds[i][c])

def set_values_by_distance(distance):
    global brightness, noise_speed, spacing
    
    # clamp distance to [20,200]
    """ if distance < MINCM:
        distance = MINCM
    elif distance > MAXCM:
        distance = MAXCM """
    
    # normalize distance to a t between 0–1
    t = (distance - MINCM) / (MAXCM - MINCM)

    brightness = lerp(1, .2, t)
    sample_points = int(lerp(150, 5, t))
    noise_speed = lerp(0.1, 0.02, t)
    spacing = (NUM_LEDS-1) / (sample_points-1)

# ----------------------------
# LED HANDLING
# ----------------------------
current_leds = [[0] * 3 for _ in range(NUM_LEDS)]
target_leds = [[0] * 3 for _ in range(NUM_LEDS)]

led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_RGB)
led_strip.start()

# ----------------------------
# MAIN
# ----------------------------

curves = [
    ((0, 0), (10, 0), (10, 10)),
    ((10, 10), (6, 14), (2, 10)),
    ((2, 10), (2, 0), (12, 0)),
]
points = stitch_quadratic_beziers(curves, NUM_LEDS, steps_per_curve=50)  # fewer steps for speed

frame = 0
last_time = time.ticks_ms()  # record the first timestamp


sample_points = 5
spacing = (NUM_LEDS-1) / (sample_points-1)

MAXCM = 100
MINCM = 20

while True:
    # t is the offset for the noise
    t = frame * noise_speed

    # compute noise just for in SAMPLE_POINTS
    samples = []
    for s in range(sample_points):
        px, py = points[int(s * spacing)]
        n = noise2(px + t, py + t * NOISE_Y_OFFSET)
        # TODO: APPLY FLICKER BRIGHTNESS OF INDIVIDUAL LED
        samples.append(color_from_palette(n, brightness))

    # interpolate for all NUM_LEDS
    for led in range(NUM_LEDS):
        seg = led / spacing
        idx = int(seg)
        frac = seg - idx
        if idx >= sample_points-1:
            target_leds[led] = samples[-1]
        else:
            target_leds[led] = lerp_color(samples[idx], samples[idx+1], frac)
        
        # Scale each RGB component by a random factor
        if .05 > uniform(0, 1):
            r, g, b = target_leds[led]
            target_leds[led] = (
                int(200), 
                int(200), 
                int(200)
            )
    
    move_to_target()
    display_current()
    frame += 1

    # DELTA
    now = time.ticks_ms()
    delta = time.ticks_diff(now, last_time)
    last_time = now

    """ if frame % 5 == 0:
        print("Delta FPS:", 1000/delta) """

    if frame % 10 == 0:
        distance = get_distance()
        # if no sensor use the sin function below
        # distance = 20 + (100-20) * (math.sin(2*math.pi*frame/1000) + 1) / 2
        print(distance, "cm")
        set_values_by_distance(distance)
        
    # if frame % 100: 
    #     brightness_array = [uniform(.25, 1) for _ in range(NUM_LEDS)]

