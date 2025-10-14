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

def draw_battery(draw, x, y, level, w=100, h=6, padding=2):
	"""Draw a horizontal loading-bar style battery at (x,y) with width w and height h.
	level: 0..4 meaning 0%,25%,50%,75%,100% - we fill fraction = level/4. Glued to top inner border by caller.
	x,y correspond to the left-top of the bar area."""
	# Accept either percentage (0..100) or legacy level (0..4)
	fill_pct = 0
	try:
		lvl = float(level)
		if lvl <= 4:
			# legacy mode: map 0..4 to 0..100
			fill_pct = int((lvl / 4.0) * 100)
		else:
			# assume it's already a percent value
			fill_pct = int(max(0, min(100, lvl)))
	except Exception:
		fill_pct = 0
	inner_w = w - 2 * padding
	fill_w = int(inner_w * (fill_pct / 100.0))
	# do not draw outer frame; render only the filled portion so the bar looks like a loading strip
	if fill_w > 0:
		draw.rectangle((x + padding, y + (h - (h - padding))//2, x + padding + fill_w, y + h - (h - padding)//2), outline=0, fill=0)


def draw_temp_box(image_draw, pos_y, height, room_name=None, temp_c=None, humidity=None, battery_level=0):
	# make boxes use full width of epaper (no extra side margins)
	pos_x = 0
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

	# If sensor values provided, draw them with updated layout per feedback
	# compute inner content area (respect border)
	inner_left = pos_x + border - 1
	inner_right = pos_x + width - border + 1
	inner_width = inner_right - inner_left
	# Room letter: align to the left side of the right block with some inset from inner_right
	right_block_margin = 22
	label_x = inner_right - right_block_margin
	label_y = pos_y + 6
	if room_name is not None:
		# single letter (first char)
		rn = str(room_name).strip()
		if len(rn) > 0:
			rn = rn[0].upper()
		else:
			rn = '?'
		image_draw.text((label_x, label_y), rn, font=small_font, fill=0)

	# Top-right: battery drawn as up to 4 small square boxes on the top of the box
	if battery_level is not None:
		# horizontal loading bar placed inside the box just below the top border
		# height equals the border thickness and starts directly after the left black border
		bar_h = border
		bar_padding = 1
		# start exactly at the inner left (touching the inner border)
		bx = inner_left
		# place just below the top black border (inside the white area)
		by = pos_y + border
		# width spans the inner area with minimal right margin
		bar_w = inner_width - 2
		draw_battery(image_draw, bx, by, battery_level, w=bar_w, h=bar_h, padding=bar_padding)

	# Temperature: smaller than clock font and placed toward the left-middle of the top area
	if temp_c is not None:
		# use a slightly smaller font for the temperature (reduce size by ~6)
		try:
			temp_font = ImageFont.truetype("./res/monofonto.otf", max(12, font.size - 6))
		except Exception:
			temp_font = small_font
		# build parts to control spacing: integer, dot, fraction, degree, C
		temp_str = f"{temp_c:.1f}"
		if '.' in temp_str:
			left, right = temp_str.split('.')
		else:
			left, right = temp_str, ''
		deg = '°'
		unit = 'C'
		# measure widths
		left_w = temp_font.getlength(left)
		dot_w = temp_font.getlength('.')
		right_w = temp_font.getlength(right)
		deg_w = temp_font.getlength(deg)
		unit_w = temp_font.getlength(unit)
		total_w = left_w + dot_w + right_w + deg_w + unit_w
		# move temperature left a bit so it doesn't clash with the room letter on the right
		tx_base = inner_left + int((inner_width - total_w) * 0.18)
		ty = pos_y + 6 + 2  # move 2 px down for visual balance
		# draw left part
		x = tx_base
		image_draw.text((x, ty), left, font=temp_font, fill=0)
		x += left_w
		# draw dot slightly left (overlap) to reduce gap
		overlap_dot = 2
		image_draw.text((x - overlap_dot, ty), '.', font=temp_font, fill=0)
		x = x - overlap_dot + dot_w
		# draw fraction with slight overlap
		overlap_frac = 2
		image_draw.text((x - overlap_frac, ty), right, font=temp_font, fill=0)
		x = x - overlap_frac + right_w
		# draw degree symbol with small left overlap
		overlap_deg = 2
		image_draw.text((x - overlap_deg, ty), deg, font=temp_font, fill=0)
		x = x - overlap_deg + deg_w
		# draw unit 'C' with small left overlap
		overlap_unit = 1
		image_draw.text((x - overlap_unit, ty), unit, font=temp_font, fill=0)

	# Humidity: bottom-right inside the box
	if humidity is not None:
		# left-align humidity under the room letter with padding
		hum_text = f"{int(humidity)}%"
		hf_w = small_font.getlength(hum_text)
		# ensure humidity text does not overflow into the right border
		small_margin = 4
		hx = label_x
		if hx + hf_w > inner_right - small_margin:
			hx = inner_right - small_margin - hf_w
		hy = label_y + 18
		image_draw.text((hx, hy), hum_text, font=small_font, fill=0)

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
	{"name": "Living", "temp": 21.3, "hum": 45, "bat": 97},
	{"name": "Kitchen", "temp": 23.8, "hum": 50, "bat": 12},
	{"name": "Bedroom", "temp": 19.6, "hum": 55, "bat": 35},
	{"name": "Office", "temp": 20.1, "hum": 48, "bat": 67},
]

box_y = 59
box_h = 45
for i, r in enumerate(rooms):
	y = box_y + i * (box_h + 4)
	draw_temp_box(time_draw, pos_y=y, height=box_h, room_name=r['name'], temp_c=r['temp'], humidity=r['hum'], battery_level=r['bat'])

epd.display(epd.getbuffer(time_image))
epd.sleep()


