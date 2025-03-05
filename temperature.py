import sys
import os

import epaper
import time
from PIL import Image,ImageDraw,ImageFont

font24 = ImageFont.truetype("./res/boxy-bold.ttf", 24)

epd = epaper.epaper('epd2in13_V4').EPD()
epd.init()
epd.Clear(0xFF)

time_image = Image.new('1', (epd.width, epd.height), 255)
time_image.rotate(90)
time_draw = ImageDraw.Draw(time_image)
epd.displayPartBaseImage(epd.getbuffer(time_image))
while (True):
	time_draw.rectangle((2, 10, 100, 34), fill = 255)
	string_var=time.strftime('%H:%M')
	string_var = " ".join(c for c in string_var)

	time_draw.text((2, 20), string_var, font=font24, fill = 0, align="center")
	epd.displayPartial(epd.getbuffer(time_image))

