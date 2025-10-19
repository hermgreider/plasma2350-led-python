import random
import math
import plasma
import time
import machine

# SONIC-NOISE-REFINED.PY

TRIG = machine.Pin(28, machine.Pin.OUT)   
ECHO = machine.Pin(19, machine.Pin.IN)  # (with voltage divider)


def get_points_on_circle(center, radius, num_points):
    cx, cy = center
    return [
        ((
            cx + radius * math.cos(2 * math.pi * i / num_points),
            cy + radius * math.sin(2 * math.pi * i / num_points)
        ), i)
        for i in range(num_points)
    ]


def clamp(value, min_val=0.0, max_val=1.0):
    """Clamp a number between min_val and max_val."""
    return max(min_val, min(max_val, value))


def get_color_indices(value, num_colors):
    """
    Given a normalized value [0,1], find the two color indices
    to interpolate between and the local interpolation factor t.
    """
    n = num_colors - 1
    scaled = value * n
    i = int(scaled)
    j = i + 1
    t = scaled - i
    return i, j, t


def lerp(a, b, t):
    """Linear interpolation between a and b by normalized value t."""
    return a * (1 - t) + b * t


def inverse_lerp(a, b, x):
    """ Inverse Interpolation to normalize x by a and b"""
    return (x - a) / (b - a)


def nudge(current, target, up_speed, down_speed):
    """ Eases or nudges the current toward the target by factor speed """
    if current < target:
        return min(current + up_speed, target)
    elif current > target:
        return max(current - down_speed, target)
    return current


def height_to_hue(height, hues):
    """
    Map a normalized value [0,1] to a color from a list of hue integers.
    Smoothly interpolates between neighboring hues.
    """
    height = clamp(height)
    i, j, t = get_color_indices(height, len(hues))
    j = min(j, len(hues) - 1)  # ensure j doesnt go out of bounds
    return lerp(hues[i],  hues[j], t)


def get_height(x, y, scale):
    """ Gets the intensity of the noise function based on position x, y, and scale """
    """
    x, y: floats, scaled position
    Returns: interpolated noise value 0-1
    """
    x = x * scale
    y = y * scale
    # Wrap around the grid
    gx = int(x) % GRID_SIZE
    gy = int(y) % GRID_SIZE
    gx1 = (gx + 1) % GRID_SIZE
    gy1 = (gy + 1) % GRID_SIZE

    fx = x - int(x)  # fractional part
    fy = y - int(y)

    # Four corners
    a = noise_grid[gy][gx]
    b = noise_grid[gy][gx1]
    c = noise_grid[gy1][gx]
    d = noise_grid[gy1][gx1]

    # Linear interpolation
    top = a + (b - a) * fx
    bottom = c + (d - c) * fx
    return top + (bottom - top) * fy



def get_distance():
    """ generates a sin betwixt 0 and 10 if distance, the unit is meters """
    # return (math.sin(frame/2) + 1) * 5
    global last_presence, last_distance_cm, distance_cm, presence

    if uart.any():
        line = uart.readline()
        if not line:
            return last_distance_cm
        # print("line is: ", line)

        try:
            text = line.decode('utf-8').strip()
        except UnicodeError:
            return distance_cm

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
    
    return distance_cm
    #return mouse_x


def refresh_values():
    # nudge values toward target
    # set new targets
    for i, value in enumerate(values):
        values[i] = nudge(value, target_values[i], flutter_speed_up, flutter_speed_down)
        if random.uniform(0, 1) < flutter_probability: # add random flutters
            target_values[i] = max_v
        if value == target_values[i]:
            target_values[i] = min_v


def set_hsv(frame):
    """ Set the LEDS """
    global flutter_probability, flutter_speed_up, flutter_speed_down, min_v
    global offset
    global hue_palette

    
    scale = clamp(inverse_lerp(10, 120, get_distance()), 0, 1) # normalized distance
    print("scale: ", scale)
    offset = frame * .05
    """ # smaller scale → faster x, y offset
    min_speed = 0.002
    max_speed = .5
    speed = min_speed + (1 - scale) * (max_speed - min_speed)

    # Increment offset linearly, scaled by speed
    offset += speed
    #print('%.3f'%speed, '%.3f'%offset) """

    flutter_probability = lerp(.2, .02, scale)
    flutter_speed_up = lerp(.15, .1, scale)
    flutter_speed_down = lerp(.09, .02, scale)
    #min_v = lerp(.25, .25, scale)
    # print("flutter:", flutter_probability, flutter_speed_up, flutter_speed_down)
    
    color_scale = lerp(.01, .1, scale)
    refresh_values()
    #hue_palette = [color - color_scale for color in hue_palette]
    print(hue_palette)

    for (x, y), i in points:
        # Add time offset for flowing noise3
        # print("getting height with", x, y, offset, scale)
        height = get_height(x + offset, y + offset * 0.3, scale)
        hue = height_to_hue(height, hue_palette) # Map noise to leds
        saturation = lerp(.75, 1, 1 - scale) # normalize and invert value for s
        hsv = (hue, saturation, values[i])
        # LEDS[i] = (i,hsv)
        led_strip.set_hsv(i, hue, saturation, values[i])
        # set dots with converted hsv
    

    
    #time.sleep(1)
    return True



# region boilerplate

# region LED HANDLING
NUM_LEDS = 120
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_RGB)
led_strip.start()

LEDS = [(0, 0, 0)] * NUM_LEDS  # preallocate memory
#endregion

# region FLUTTER
flutter_probability = .02
flutter_speed_up = .05
flutter_speed_down = .2
min_v = .25
max_v = .75
values = [min_v] * NUM_LEDS
target_values = [min_v] * NUM_LEDS # the target to lerp towards
#endregion

#region OTHER
frame = 0
offset = 0
points = get_points_on_circle((0, 0), 10, NUM_LEDS) # Get evenly spaced points along all curves
GRID_SIZE = 16
noise_grid = [[random.random() for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


#endregion

#region SENSOR
# UART0 on Pimoroni Plasma 2350
uart = machine.UART(0, baudrate=115200, tx=machine.Pin(0), rx=machine.Pin(1), bits=8, parity=None, stop=1)

print("HMMD mmWave Sensor (text mode) reader started...")

presence = None
distance_cm = 0.0
last_presence = False
last_distance_cm = 1000.0

#endregion
#hue_palette = [0, .05, .1, .2, .3]
#hue_palette = [.3, .38, .4, .58, .62]
initial_hue_palette = [.36, .37, .38, .4, .6]
hue_palette = [.36, .37, .38, .4, .6]

#endregion

 
# region LED loop
while True:
    last_time = time.ticks_ms()  # record the first timestamp
    set_hsv(frame)
    # frame boilerplate
    now = time.ticks_ms() 
    
    delta = time.ticks_diff(now, last_time)
    last_time = now

    frame += 1

    """ if frame % 10 == 0:
        print("Delta FPS:", 1000/delta) """

# endregion