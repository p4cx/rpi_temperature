try:
	import epaper
except Exception:
	epaper = None
import time
from PIL import Image,ImageDraw,ImageFont

font = ImageFont.truetype("./res/monofonto.otf", 35)
small_font = ImageFont.truetype("./res/monofonto.otf", 16)
epaper_size = (122, 250)

# Layout constants
CLOCK_HEIGHT = 48
GAP_AFTER_CLOCK = 2
BOX_HEIGHT = 46
INTER_BOX_GAP = 4
# After this many partial updates, force a full screen refresh
FULL_UPDATE_AFTER_PARTIALS = 10

if epaper is not None:
	epd = epaper.epaper('epd2in13_V4').EPD()
	epd.init()
	epd.Clear(0xFF)
	# log available epd attributes for debugging driver compatibility
	try:
		attrs = sorted(dir(epd))
		print("EPD attributes:")
		print('\n'.join(attrs))
	except Exception as e:
		print("Could not list epd attributes:", e)
else:
	# Dummy epd replacement for development on non-RPi machines
	class _DummyEPD:
		def init(self):
			print("DummyEPD.init()")
		def Clear(self, v):
			print(f"DummyEPD.Clear({v})")
		def display(self, buffer):
			try:
				from PIL import Image
				import os
				os.makedirs('./res/preview', exist_ok=True)
				if isinstance(buffer, Image.Image):
					image = buffer
				else:
					try:
						image = Image.frombytes('1', epaper_size, buffer)
					except Exception:
						image = None
				if image is not None:
					fname = time.strftime('res/preview/preview_%Y%m%d_%H%M%S.png')
					image.convert('RGB').save(fname)
					print(f"DummyEPD.display() saved preview to {fname}")
				else:
					print("DummyEPD.display() called but could not create image from buffer")
			except Exception as e:
				print("DummyEPD.display() error:", e)
			return
		def getbuffer(self, pil_image):
			try:
				return pil_image
			except Exception:
				return b''
		def sleep(self):
			print("DummyEPD.sleep()")

	epd = _DummyEPD()
	epd.init()
	epd.Clear(0xFF)

def draw_box(image_draw, pos_y, height, room_name=None, temp_c=None, humidity=None, battery_level=0, clock_text=None):
	width = epaper_size[0]
	pos_x = 0
	# simple frame parameters
	border = 4
	cut = 10

		# normal box: outer black polygon with a cut-off top-right corner for style
	image_draw.polygon((
		(pos_x, pos_y),
		(pos_x + (width - 2 * pos_x) - cut, pos_y),
		(pos_x + (width - 2 * pos_x), pos_y + cut),
		(pos_x + (width - 2 * pos_x), pos_y + height),
		(pos_x, pos_y + height)
		), fill=0)
	# inner white area (frame effect) with matching small cut at top-right
	inner_left = pos_x + border
	inner_right = pos_x + width - border

	# Clock mode: full-width black box with centered white time
	if clock_text is not None:
		# center text
		font_to_use = font
		try:
			text_width = font_to_use.getlength(clock_text)
			text_x = pos_x + (width - text_width) / 2
			preferred_y = pos_y + (height - font_to_use.size) / 2 - 6
			text_y = max(pos_y + 2, preferred_y)
		except Exception:
			text_x = pos_x + 8
			text_y = pos_y + 4
		image_draw.text((text_x, text_y), clock_text, font=font_to_use, fill=255)
		return image_draw
	else:
		image_draw.polygon((
			(pos_x + border, pos_y + border),
			(pos_x + border + (width - 2 * (pos_x + border * 0.65)) - cut, pos_y + border),
			(pos_x + border + (width - 2 * (pos_x + border)), pos_y + cut + border * 0.5),
			(pos_x + border + (width - 2 * (pos_x + border)), pos_y + height - border),
			(pos_x + border, pos_y + height - border)
			), fill=255)

	inner_width = inner_right - inner_left

	# room letter on the right side
	right_block_margin = 22
	label_x = inner_right - right_block_margin
	label_y = pos_y + 6
	if room_name is not None:
		rn = str(room_name).strip()
		if len(rn) > 0:
			rn = rn[0].upper()
		else:
			rn = '?'
		image_draw.text((label_x, label_y), rn, font=small_font, fill=0)

	# battery as a horizontal loading bar just below the top inner border
	if battery_level is not None:
		bar_h = max(3, border - 1)
		bx = inner_left
		by = pos_y + border - 1
		bar_w = inner_width - 2
		fill_pct = 0
		try:
			lvl = float(battery_level)
			fill_pct = int(max(0, min(100, lvl)))
		except Exception:
			fill_pct = 0
		fill_w = int(bar_w * (fill_pct / 100.0))
		if fill_w > 0:
			image_draw.rectangle((bx, by + (bar_h - (bar_h))//2, bx + fill_w, by + bar_h - (bar_h)//2), outline=0, fill=0)

	# temperature on the left/top area
	if temp_c is not None:
		try:
			temp_font = ImageFont.truetype("./res/monofonto.otf", max(12, font.size - 6))
		except Exception:
			temp_font = small_font
		temp_str = f"{temp_c:.1f}"
		if '.' in temp_str:
			left, right = temp_str.split('.')
		else:
			left, right = temp_str, ''
		deg = '°'
		unit = 'C'
		left_w = temp_font.getlength(left)
		dot_w = temp_font.getlength('.')
		right_w = temp_font.getlength(right)
		deg_w = temp_font.getlength(deg)
		unit_w = temp_font.getlength(unit)
		total_w = left_w + dot_w + right_w + deg_w + unit_w
		tx_base = inner_left + int((inner_width - total_w) * 0.1)
		ty = pos_y + 6
		x = tx_base
		image_draw.text((x, ty), left, font=temp_font, fill=0)
		x += left_w
		overlap_dot = 3
		image_draw.text((x - overlap_dot, ty), '.', font=temp_font, fill=0)
		x = x - overlap_dot + dot_w
		overlap_frac = 3
		image_draw.text((x - overlap_frac, ty), right, font=temp_font, fill=0)
		x = x - overlap_frac + right_w
		overlap_deg = 0
		image_draw.text((x - overlap_deg, ty), deg, font=temp_font, fill=0)
		x = x - overlap_deg + deg_w
		overlap_unit = 3
		image_draw.text((x - overlap_unit, ty), unit, font=temp_font, fill=0)

	# humidity bottom-right inside inner area
	if humidity is not None:
		hum_text = f"{int(humidity)}%"
		hf_w = small_font.getlength(hum_text)
		small_margin = 2
		hx = label_x
		if hx + hf_w > inner_right - small_margin:
			hx = inner_right - small_margin - hf_w
		hy = label_y + 18
		image_draw.text((hx, hy), hum_text, font=small_font, fill=0)

	return image_draw


def render_once():
	# Sample sensor data for four rooms. In real usage replace these with live readings.
	rooms = [
		{"name": "Living", "temp": 1.3, "hum": 100, "bat": 5},
		{"name": "Kitchen", "temp": 23.8, "hum": 50, "bat": 12},
		{"name": "Bedroom", "temp": 19.6, "hum": 55, "bat": 35},
		{"name": "Office", "temp": 20.1, "hum": 48, "bat": 67},
	]

	display_image = Image.new('1', epaper_size, 255)
	# rotation is a no-op for the image object; we keep orientation consistent with earlier code
	display_draw = ImageDraw.Draw(display_image)

	time_string = time.strftime('%H:%M')

	box_y = 0
	# First draw clock box using layout constants
	draw_box(display_draw, pos_y=box_y, height=CLOCK_HEIGHT, clock_text=time_string)
	# Draw four temp boxes below the clock box
	for i, r in enumerate(rooms):
		y = box_y + CLOCK_HEIGHT + GAP_AFTER_CLOCK + i * (BOX_HEIGHT + INTER_BOX_GAP)
		draw_box(display_draw, pos_y=y, height=BOX_HEIGHT, room_name=r['name'], temp_c=r['temp'], humidity=r['hum'], battery_level=r['bat'])

	# send to epaper
	try:
		epd.display(epd.getbuffer(display_image))
		epd.sleep()
	except Exception:
		pass


def run_loop():
	# keep last rendered values for detecting changes
	last_values = {
		'minute': None,
		'rooms': [],
	}
	last_full_image = None

	poll_interval = 5.0  # seconds between checks
	partial_update_counter = 0
	try:
		while True:
			now = time.time()
			cur_min = time.strftime('%Y-%m-%d %H:%M', time.localtime(now))

			# get current sensor data (replace this with real data retrieval)
			rooms = [
				{"name": "Living", "temp": 1.3, "hum": 45, "bat": 5},
				{"name": "Kitchen", "temp": 23.8, "hum": 50, "bat": 12},
				{"name": "Bedroom", "temp": 19.6, "hum": 55, "bat": 35},
				{"name": "Office", "temp": 20.1, "hum": 48, "bat": 67},
			]

			if last_values['minute'] != cur_min:
				full_image = Image.new('1', epaper_size, 255)
				full_drawer = ImageDraw.Draw(full_image)
				time_string = time.strftime('%H:%M')
				box_y = 0
				draw_box(full_drawer, pos_y=box_y, height=CLOCK_HEIGHT, clock_text=time_string)
				for i, room in enumerate(rooms):
					y = box_y + CLOCK_HEIGHT + GAP_AFTER_CLOCK + i * (BOX_HEIGHT + INTER_BOX_GAP)
					draw_box(full_drawer, pos_y=y, height=BOX_HEIGHT, room_name=room['name'], temp_c=room['temp'], humidity=room['hum'], battery_level=room['bat'])
				last_values['rooms'] = rooms
				try:
					epd.display(epd.getbuffer(full_image))
					epd.sleep()
				except Exception:
					pass

	except KeyboardInterrupt:
		try:
			epd.sleep()
		except Exception:
			pass
		print('Exiting')


if __name__ == '__main__':
	run_loop()


