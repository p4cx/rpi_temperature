import sys
import os

try:
	import epaper
except Exception:
	epaper = None
import time
from PIL import Image,ImageDraw,ImageFont

debug = True
font = ImageFont.truetype("./res/monofonto.otf", 35)
# smaller font for labels / humidity
small_font = ImageFont.truetype("./res/monofonto.otf", 16)
epaper_size = (122, 250)

if epaper is not None:
	epd = epaper.epaper('epd2in13_V4').EPD()
	epd.init()
	epd.Clear(0xFF)
else:
	# Dummy epd replacement for development on non-RPi machines
	class _DummyEPD:
		def init(self):
			print("DummyEPD.init()")
		def Clear(self, v):
			print(f"DummyEPD.Clear({v})")
		def display(self, buf):
			# for testing, save image buffer to file if it's a PIL Image or raw bytes
			try:
				from PIL import Image
				import os
				# ensure preview directory exists
				os.makedirs('./res/preview', exist_ok=True)
				if isinstance(buf, Image.Image):
					img = buf
				else:
					# try to interpret as raw bytes for a 1-bit image
					try:
						img = Image.frombytes('1', epaper_size, buf)
					except Exception:
						img = None
				if img is not None:
					fname = time.strftime('res/preview/preview_%Y%m%d_%H%M%S.png')
					# convert to RGB so PNG viewers render correctly
					img.convert('RGB').save(fname)
					print(f"DummyEPD.display() saved preview to {fname}")
				else:
					print("DummyEPD.display() called but could not create image from buffer")
			except Exception as e:
				print("DummyEPD.display() error:", e)
			return
		def getbuffer(self, image):
			# Return the PIL Image directly so display can save it for preview
			try:
				return image
			except Exception:
				return b''
		def sleep(self):
			print("DummyEPD.sleep()")

	epd = _DummyEPD()
	epd.init()
	epd.Clear(0xFF)

def draw_battery(draw, x, y, level, w=28, h=12):
	"""Draw a small horizontal battery at (x,y). level: 0..4 filled segments."""
	# battery body
	draw.rectangle((x, y, x + w, y + h), outline=0, fill=255)
	# battery nub
	nub_w = 3
	nub_h = h // 2
	draw.rectangle((x + w, y + (h - nub_h) // 2, x + w + nub_w, y + (h + nub_h) // 2), outline=0, fill=255)
	# segments
	segs = 4
	inner_x = x + 2
	inner_y = y + 2
	inner_w = w - 4
	inner_h = h - 4
	seg_w = inner_w / segs
	for i in range(segs):
		sx = inner_x + i * seg_w
		ex = sx + seg_w - 2
		if i < level:
			draw.rectangle((sx, inner_y, ex, inner_y + inner_h), outline=0, fill=0)
		else:
			draw.rectangle((sx, inner_y, ex, inner_y + inner_h), outline=0, fill=255)


def draw_temp_box(image_draw, pos_y, height, room_name=None, temp_c=None, humidity=None, battery_level=0):
	pos_x = 4
	width = epaper_size[0]
	cut = 10
	border = 4
	# outer filled polygon (box background)
	image_draw.polygon((
		(pos_x, pos_y),
		(pos_x + (width - 2 * pos_x) - cut, pos_y),
		(pos_x + (width - 2 * pos_x), pos_y + cut),
		(pos_x + (width - 2 * pos_x), pos_y + height),
		(pos_x, pos_y + height)
		), fill=0)
	# inner cutout
	image_draw.polygon((
		(pos_x + border, pos_y + border),
		(pos_x + border + (width - 2 * (pos_x + border * 0.65)) - cut, pos_y + border),
		(pos_x + border + (width - 2 * (pos_x + border)), pos_y + cut + border * 0.5),
		(pos_x + border + (width - 2 * (pos_x + border)), pos_y + height - border),
		(pos_x + border, pos_y + height - border)
		), fill=255)

	# If sensor values provided, draw them
	content_left = pos_x + 8
	content_top = pos_y + 4
	# room name
	if room_name is not None:
		image_draw.text((content_left, content_top), str(room_name), font=small_font, fill=0)

	# humidity and battery on the left-bottom
	if humidity is not None:
		hum_text = f"{int(humidity)}%"
		# place humidity under room name
		image_draw.text((content_left, pos_y + height - 18), hum_text, font=small_font, fill=0)

	if battery_level is not None:
		# draw battery to the right of humidity
		bx = pos_x + 60
		by = pos_y + height - 20
		# clamp battery_level to 0..4
		try:
			bl = int(battery_level)
		except Exception:
			bl = 0
		bl = max(0, min(4, bl))
		draw_battery(image_draw, bx, by, bl)

	# temperature on the right, large
	if temp_c is not None:
		temp_text = f"{temp_c:.1f}°C"
		# center vertically in the box, align right
		t_w = font.getlength(temp_text)
		tx = pos_x + (width - 2 * pos_x) - t_w - 8
		ty = pos_y + (height - font.size) / 2
		image_draw.text((tx, ty), temp_text, font=font, fill=0)

	return image_draw



time_image = Image.new('1', (122, 250), 255)
time_image.rotate(90)
time_draw = ImageDraw.Draw(time_image)
time_draw.rectangle((0, 0, 122, 55), fill = 0)
string_var=time.strftime('%H:%M')
hello = font.getlength(string_var)
time_draw.text(((122-hello)/2, 7), string_var, font=font, fill = 255, align="center")

# Sample sensor data for four rooms. In real usage replace these with live readings.
rooms = [
	{"name": "Living", "temp": 21.3, "hum": 45, "bat": 4},
	{"name": "Kitchen", "temp": 23.8, "hum": 50, "bat": 3},
	{"name": "Bedroom", "temp": 19.6, "hum": 55, "bat": 2},
	{"name": "Office", "temp": 20.1, "hum": 48, "bat": 1},
]

box_y = 59
box_h = 45
for i, r in enumerate(rooms):
	y = box_y + i * (box_h + 4)
	draw_temp_box(time_draw, pos_y=y, height=box_h, room_name=r['name'], temp_c=r['temp'], humidity=r['hum'], battery_level=r['bat'])

epd.display(epd.getbuffer(time_image))
epd.sleep()


