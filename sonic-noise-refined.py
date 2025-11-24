import random
import math
import plasma
import time
import machine

# SONIC-NOISE-REFINED.PY

class CurrentMinMax:
    def __init__(self, current, min, max):
        self.current = current
        self.min = min
        self.max = max

class Daisy:
    def __init__(self, envelope, patch):
        self.envelope = envelope
        self.patch = patch

class Config:
    def __init__(self, hue_palette, color_shift_factor, smooth_factor, flutter_probability: CurrentMinMax, flutter_speed_up: CurrentMinMax, flutter_speed_down: CurrentMinMax, value: CurrentMinMax, distance: CurrentMinMax):
        self.hue_palette = hue_palette
        self.scale_multiplier = color_shift_factor
        self.smooth_factor = smooth_factor

        self.flutter_probability = flutter_probability
        self.flutter_speed_up = flutter_speed_up
        self.flutter_speed_down = flutter_speed_down

        self.value = value
        self.distance = distance



""" def get_points_on_circle(center, radius, num_points):
    cx, cy = center
    return [
        ((
            cx + radius * math.cos(2 * math.pi * i / num_points),
            cy + radius * math.sin(2 * math.pi * i / num_points)
        ), i)
        for i in range(num_points)
    ] """

def get_points_on_line(start, end, num_points):
    x1, y1 = start
    x2, y2 = end

    return [
        ((x1 + (x2 - x1) * i / (num_points - 1),
          y1 + (y2 - y1) * i / (num_points - 1)), i)
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

def circular_lerp(a, b, t):
    """ lerps along the shortest wrapped path """
    diff = (b - a + 0.5) % 1.0 - 0.5  # shortest direction
    return (a + diff * t) % 1.0
 

def nudge(current, target, up_speed, down_speed):
    """ Eases or nudges the current toward the target by factor speed """
    if current < target:
        return min(current + up_speed, target)
    elif current > target:
        return max(current - down_speed, target)
    return current

def nudge_hue(current, target, up_speed, down_speed):
    """ Eases or nudges the current toward the target by factor speed """
    # Smallest signed distance on a circular 0–1 hue wheel
    diff = (target - current + 0.5) % 1.0 - 0.5

    # Move toward the target like your nudge()
    if diff > 0:
        current += min(diff, up_speed)
    else:
        current += max(diff, - down_speed)

    return current % 1.0


def hue(hue):
    """ normalizes and wraps hue value """
    return (float(hue) % 360.0) / 360.0

def height_to_hue(height, hues):
    """
    Map a normalized value [0,1] to a color from a list of hue integers.
    Smoothly interpolates between neighboring hues.
    """
    height = clamp(height)
    i, j, t = get_color_indices(height, len(hues))
    j = min(j, len(hues) - 1)  # ensure j doesnt go out of bounds
    return circular_lerp(hues[i],  hues[j], t)
    return hues[j]


def get_height(x, y, scale):
    """ Gets the intensity of the noise function based on position x, y, and scale """
    """
    x, y: floats, scaled position
    Returns: interpolated noise value 0-1
    """
    x = x * scale / 1.25
    y = y * scale / 1.25
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
    # Dad this is the sin function for simulating the distance value
    # return (math.sin(frame/75) + 1) * 5

    global last_presence, last_distance_cm, distance_cm, presence, last_distance_ms

    if uartSensor.any():
        line = uartSensor.readline()
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
        last_distance_ms = time.time()
       
    elif last_distance_ms + 5 < time.time():
        distance_cm = SETTINGS.distance.max
        last_distance_ms = time.time()
        last_distance_cm = distance_cm
        print ("resetting to min", distance_cm)
    #distance_cm = 200.0
    return distance_cm 
    #return mouse_x


def refresh_values():
    # nudge values toward target
    # set new targets
    for i, value in enumerate(current_values):
        current_values[i] = nudge(value, target_values[i], SETTINGS.flutter_speed_up.current, SETTINGS.flutter_speed_down.current)
        if random.uniform(0, 1) < SETTINGS.flutter_probability.current: # add random flutters
            target_values[i] = SETTINGS.value.max
        if value == target_values[i]:
            target_values[i] = SETTINGS.value.min


def set_hsv():
    """ Set the LEDS """
    global SETTINGS, offset, hue_palette, smooth_scale, last_distance_cm
    SETTINGS.distance.current = get_distance()
    scale = clamp(inverse_lerp(SETTINGS.distance.min, SETTINGS.distance.max, SETTINGS.distance.current), 0, 1) # normalized distance
    smooth_scale = smooth_scale + SETTINGS.smooth_factor * (scale - smooth_scale)
    uartDaisy.write(int(smooth_scale * 255).to_bytes(1, "little"))
    # print("smooth_scale: ", smooth_scale, ", encoded: ", int(smooth_scale * 255).to_bytes(1, "little"))
    # smaller scale → faster x, y offset
    min_speed = .1
    max_speed = .2
    speed = min_speed + (1 - scale) * (max_speed - min_speed)

    # Increment offset linearly, scaled by speed
    offset += speed
    #print('%.3f'%speed, '%.3f'%offset)

    SETTINGS.flutter_probability.current = lerp(SETTINGS.flutter_probability.min, SETTINGS.flutter_probability.max, smooth_scale)
    SETTINGS.flutter_speed_up.current = lerp(SETTINGS.flutter_speed_up.min, SETTINGS.flutter_speed_up.max, smooth_scale)
    SETTINGS.flutter_speed_down.current = lerp(SETTINGS.flutter_speed_down.min, SETTINGS.flutter_speed_down.max, smooth_scale)
    #min_v = lerp(.25, .25, scale)
    
    color_scale = lerp(SETTINGS.scale_multiplier, .01, smooth_scale)
    refresh_values()
    hue_palette = [color - color_scale for color in SETTINGS.hue_palette] # for a .25 shift in hue values per scale
    # hue_palette = SETTINGS.hue_palette # for no shift in overall color palette

    for (x, y), i in points:
        # Add time offset for flowing noise3
        # print("getting height with", x, y, offset, scale)
        height = get_height(x + offset, y + offset, smooth_scale)
        target_hues[i] = height_to_hue(height, hue_palette) # Map noise to hue target
        current_hues[i] = nudge_hue(current_hues[i], target_hues[i], .5, .02) # nudge current toward target
        current_hues[i] = current_hues[i] % 1.0 # wrap along hsv scale
        saturation = lerp(.75, 1, 1 - scale) # normalize and invert value for saturation
        # LEDS[i] = (i,hsv)
        led_strip.set_hsv(i, current_hues[i], saturation, current_values[i]) 
        # set dots with converted hsv
        
    """ for (x, y), i in points:
        # Add time offset for flowing noise3
        # print("getting height with", x, y, offset, scale)
        height = get_height(x + offset, y + offset * 0.3, scale)
        hue = height_to_hue(height, hue_palette) # Map noise to hue
        # nudge current toward target
        saturation = lerp(.75, 1, 1 - scale) # normalize and invert value for s
        # LEDS[i] = (i,hsv)
        led_strip.set_hsv(i, hue % 1.0, saturation, current_values[i])
        # set dots with converted hsv """
    

    
    #time.sleep(1)
    return True

# region boilerplate
SETTINGS = Config(
    # Moogy Pad - Horiz 4 pane  pink & blue -> cyan | green
    hue_palette = [hue(120), hue(200), hue(260), hue(350)],
    color_shift_factor = .15,
    
    # Moog Bass - 6 pane    green & yellow -> red,
    # hue_palette = [hue(45), hue(65), hue(100)],
    # color_shift_factor = .15,
    
    # Bell 1 - 1 pane   pink & green -> blue | cyan
    # hue_palette = [hue(15), hue(25), hue(35), hue(70), hue(85), hue(90)], 
    # color_shift_factor = -.3,
    
    # Shaker 1 - 8 pane     cyan & purple -> deep orange
    # hue_palette =[hue(165), hue(300)],  
    # color_shift_factor = .6,
    
    # Shaker 2 - 4 pane     green & cyan -> pink | red
    # hue_palette = [hue(135), hue(170)],
    # color_shift_factor = -.5,
    
    # Moogy Pad - Tall 8 pane   red & yellow & green -> yellow | green
    # hue_palette = [hue(0), hue(75), hue(150)],
    # color_shift_factor = .15,
    
    # Moogy Pad - 4 pane    purple & cyan -> pale purple | red 
   # hue_palette =[hue(145), hue(175), hue(270), hue(310)], 
   # color_shift_factor = -.25,
    
    # Bell 2 - 8 pane   green & blue & yellow -> cyan | blue | teal
    # hue_palette = [hue(15), hue(150),hue(25), hue(145)], 
    # color_shift_factor = .75,

    smooth_factor = 0.15, # smaller = smoother, slower response
    flutter_probability = CurrentMinMax(.05, .1, .01),
    flutter_speed_up = CurrentMinMax(.05, .15, .1),
    flutter_speed_down = CurrentMinMax(.2, .09, .02),
    value = CurrentMinMax(.75, .5, 1.0),  #TODO: CHANGE THESE BACK
    distance = CurrentMinMax(90, 10, 75) #TODO: CHANGE THESE BACK to 90, 450
#    distance = CurrentMinMax(400, 300, 500)
)

# region LED HANDLING
NUM_LEDS = 120
led_strip = plasma.WS2812(NUM_LEDS, color_order=plasma.COLOR_ORDER_GRB)
led_strip.start()

LEDS = [(0, 0, 0)] * NUM_LEDS  # preallocate memory
#endregion

# region FLUTTER
current_values = [SETTINGS.value.min] * NUM_LEDS
target_values = [SETTINGS.value.min] * NUM_LEDS # the target to lerp towards
#endregion

# region HUE
current_hues = [.5] * NUM_LEDS
target_hues = [.5] * NUM_LEDS # the target to lerp towards
#endregion

#region OTHER
frame = 0
offset = 0
points = get_points_on_line((0, 0), (25, 18), NUM_LEDS) # Get evenly spaced points along all curves
GRID_SIZE = 16
noise_grid = [[random.random() for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

smooth_scale = 0  # initialize once at start


#endregion

#region SENSOR
# UART0 on Pimoroni Plasma 2350
uartSensor = machine.UART(0, baudrate=115200, tx=machine.Pin(0), rx=machine.Pin(1), bits=8, parity=None, stop=1)
uartDaisy = machine.UART(1, baudrate=9600, tx=machine.Pin(20), rx=machine.Pin(21))

print("HMMD mmWave Sensor (text mode) reader started...")

presence = None
distance_cm = 0.0
last_presence = False
last_distance_cm = 1000.0
last_distance_ms = time.time()

#endregion

hue_palette = SETTINGS.hue_palette

#endregion

 
# region LED loop
while True:
    last_time = time.ticks_ms()  # record the first timestamp
    set_hsv()
    # frame boilerplate
    now = time.ticks_ms() 
    
    delta = time.ticks_diff(now, last_time)
    last_time = now

    frame += 1

    """ if frame % 10 == 0:
        print("Delta FPS:", 1000/delta) """

# endregion