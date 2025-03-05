import sys
import os

import epaper
import time
from PIL import Image,ImageDraw,ImageFont

font24 = ImageFont.truetype("ls /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 24)

epd = epaper.epaper('epd2in13_V4').EPD()
logging.info("init and Clear")
epd.init()
epd.clear(0xFF)

time_image = Image.new('1', (epd.width, epd.height), 255)
time_image.rotate(90)
time_draw = ImageDraw.Draw(time_image)
epd.displayPartBaseImage(epd.getbuffer(time_image))
while (True):
	time_draw.rectangle((120, 80, 220, 105), fill = 255)
	time_draw.text((20, 20), time.strftime('%H:%M'), font = font24, fill = 0)
	epd.displayPartial(epd.getbuffer(time_image))

