import sys
import os

import epaper
import time
from PIL import Image,ImageDraw,ImageFont

debug = True
font = ImageFont.truetype("./res/monofonto.otf", 35)
epaper_size = (122, 250)

epd = epaper.epaper('epd2in13_V4').EPD()
epd.init()
epd.Clear(0xFF)

def draw_temp_box(image_draw, pos_y, height):
	pos_x = 4
	width = epaper_size[0]
	cut = 10
	border = 4
	image_draw.polygon((
		(pos_x, pos_y),
		(pos_x + (width - 2 * pos_x) - cut, pos_y),
		(pos_x + (width - 2 * pos_x), pos_y + cut),
		(pos_x + (width - 2 * pos_x), pos_y + height),
		(pos_x, pos_y + height)
		), fill=0)
	image_draw.polygon((
		(pos_x + border, pos_y + border),
		(pos_x + border + (width - 2 * (pos_x + border * 0.65)) - cut, pos_y + border),
		(pos_x + border + (width - 2 * (pos_x + border)), pos_y + cut + border * 0.5),
		(pos_x + border + (width - 2 * (pos_x + border)), pos_y + height - border),
		(pos_x + border, pos_y + height - border)
		), fill=255)
	return image_draw



time_image = Image.new('1', (122, 255), 255)
time_image.rotate(90)
time_draw = ImageDraw.Draw(time_image)
time_draw.rectangle((0, 0, 122, 55), fill = 0)
string_var=time.strftime('%H:%M')
hello = font.getlength(string_var)
time_draw.text(((122-hello)/2, 7), string_var, font=font, fill = 255, align="center")
# draw_temp_box(time_draw, pos_y=59, height=45)
# draw_temp_box(time_draw, pos_y=108, height=45)
# draw_temp_box(time_draw, pos_y=157, height=45)
# draw_temp_box(time_draw, pos_y=206, height=45)
epd.display(epd.getbuffer(time_image))
epd.sleep()


