from random import uniform
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


def get_random_value(ix, iy):
    """ deterministic random function, accounts for position of value """
    val = math.sin(ix * 12.9898 + iy * 78.233) * 43758.5453
    val = val - math.floor(val)
    return val


def get_height(x, y, scale):
    """ Gets the intensity of the noise function based on position x, y, and scale """
    x = x * scale
    y = y * scale
    # Bilinear Interpolation function
    cell_x = math.floor(x)   # -> X coordinate (lower-left corner)
    cell_y = math.floor(y)   # -> Y coordinate (lower-left corner)
    offset_x = x - cell_x    # -> fractional offset inside the cell along X
    offset_y = y - cell_y    # -> fractional offset inside the cell along Y
    # pass in the boundaries
    a = get_random_value(cell_x, cell_y)
    b = get_random_value(cell_x + 1.0, cell_y)
    c = get_random_value(cell_x, cell_y + 1.0)
    d = get_random_value(cell_x + 1.0, cell_y + 1.0)
    u = offset_x * offset_x * (3.0 - 2.0 * offset_x)  # smoothstep function
    v = offset_y * offset_y * (3.0 - 2.0 * offset_y)  # smoothstep function

    instensity = (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v
    return instensity


def get_distance():
    """ generates a sin betwixt 0 and 10 if distance, the unit is meters """
    return (math.sin(frame/2) + 1) * 5
    #return mouse_x


def refresh_values():
    # nudge values toward target
    # set new targets
    for i, value in enumerate(values):
        values[i] = nudge(value, target_values[i], flutter_speed_up, flutter_speed_down)
        if uniform(0, 1) < flutter_probability: # add random flutters
            target_values[i] = max_v
        if value == target_values[i]:
            target_values[i] = min_v


def set_hsv(frame):
    """ Set the LEDS """
    global flutter_probability, flutter_speed_up, flutter_speed_down, min_v
    global offset

    
    scale = clamp(inverse_lerp(-11, 11, get_distance()), 0, 1) # normalized distance
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
   #  print("flutter:", flutter_probability, flutter_speed_up, flutter_speed_down)

    refresh_values()

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
NUM_LEDS = 144
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_RGB)
led_strip.start()

LEDS = [(0, 0, 0)] * NUM_LEDS  # preallocate memory
#endregion

# region FLUTTER
flutter_probability = .02
flutter_speed_up = .05
flutter_speed_down = .2
min_v = .2
max_v = .75
values = [min_v] * NUM_LEDS
target_values = [min_v] * NUM_LEDS # the target to lerp towards
#endregion

#region OTHER
frame = 0
offset = 0
points = get_points_on_circle((0, 0), 10, NUM_LEDS) # Get evenly spaced points along all curves
#endregion


hue_palette = [0, .05, .1, .2, .3]
# hue_palette = [.3, .38, .4, .58, .62]

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

    if frame % 10 == 0:
        print("Delta FPS:", 1000/delta)

# endregion