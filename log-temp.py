#!/usr/bin/env python3

import time
import colorsys
import os
import sys
import ST7735
from bme280 import BME280
from subprocess import PIPE, Popen
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from fonts.ttf import RobotoMedium as UserFont
import logging
import logging.handlers
from requests import exceptions, post

class RequestsHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        try:
        return post(
            'https://shedtemp.pythonanywhere.com/temp',
            json={"message": msg},
            headers={"Content-type": "application/json"}
        ).content
        except exceptions.ConnectionError:
            return "Failed API"


log_formatter = logging.Formatter('%(asctime)s.%(msecs)03d,%(message)s', datefmt="%Y-%m-%d %H:%M:%S")
log_handler = logging.handlers.TimedRotatingFileHandler("temp_logs/temp.log", when="midnight")
log_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.addHandler(log_handler)
logger.addHandler(RequestsHandler())
logger.setLevel(logging.INFO)


# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# Create ST7735 LCD display class
st7735 = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=90,
    spi_speed_hz=10000000
)

# Initialize display
st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Set up canvas and font
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
path = os.path.dirname(os.path.realpath(__file__))
font_size = 20
font = ImageFont.truetype(UserFont, font_size)

message = ""

# The position of the top bar
top_pos = 25


# Displays data and text on the 0.96" LCD
def display_temp(temp):
    global values
    # Maintain length of list
    values = values[1:] + [temp]
    # Scale the values for the variable between 0 and 1
    vmin = min(values)
    vmax = max(values)
    colours = [(v - vmin + 1) / (vmax - vmin + 1) for v in values]
    # Format the variable name and value
    message = "{:.2f}".format(temp)
    draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))
    for i in range(len(colours)):
        # Convert the values to colours from red to blue
        colour = (1.0 - colours[i]) * 0.6
        r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour, 1.0, 1.0)]
        # Draw a 1-pixel wide rectangle of colour
        draw.rectangle((i, top_pos, i + 1, HEIGHT), (r, g, b))
        # Draw a line graph in black
        line_y = HEIGHT - (top_pos + (colours[i] * (HEIGHT - top_pos))) + top_pos
        draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))
    # Write the text at the top in black
    draw.text((0, 0), message, font=font, fill=(0, 0, 0))
    st7735.display(img)


# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])


# Tuning factor for compensation. Decrease this number to adjust the
# temperature down, and increase to adjust up
factor = 2.75

cpu_temps = []
for _ in range(5):
    cpu_temps.append(get_cpu_temperature())
    bme280.get_temperature()

# Create a values dict to store the data
values = [1] * WIDTH

# The main loop
try:
    while True:
        time.sleep(59.5)
        cpu_temp = get_cpu_temperature()
        # Smooth out with some averaging to decrease jitter
        cpu_temps = cpu_temps[1:] + [cpu_temp]
        avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
        raw_temp = bme280.get_temperature()
        adj_temp = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
        logger.info("Avg CPU:{:.3f}, Raw Temp:{:.3f}, Adj Temp:{:.3f}".format(avg_cpu_temp,raw_temp,adj_temp))
        display_temp(adj_temp)

# Exit cleanly
except KeyboardInterrupt:
    sys.exit(0)
