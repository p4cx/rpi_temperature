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
		def display(self, buffer):
			# for testing, save image buffer to file if it's a PIL Image or raw bytes
			try:
				from PIL import Image
				import os
				# ensure preview directory exists
				os.makedirs('./res/preview', exist_ok=True)
				if isinstance(buffer, Image.Image):
					image = buffer
				else:
					# try to interpret as raw bytes for a 1-bit image
					try:
						image = Image.frombytes('1', epaper_size, buffer)
					except Exception:
						image = None
				if image is not None:
					fname = time.strftime('res/preview/preview_%Y%m%d_%H%M%S.png')
					# convert to RGB so PNG viewers render correctly
					image.convert('RGB').save(fname)
					print(f"DummyEPD.display() saved preview to {fname}")
				else:
					print("DummyEPD.display() called but could not create image from buffer")
			except Exception as e:
				print("DummyEPD.display() error:", e)
			return
		def getbuffer(self, pil_image):
			# Return the PIL Image directly so display can save it for preview
			try:
				return pil_image
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


def draw_box(image_draw, pos_y, height, room_name=None, temp_c=None, humidity=None, battery_level=0, clock_text=None):
	# unified box drawer: can render a temperature box or a clock box when clock_text is provided
	# make boxes use full width of epaper (no extra side margins)
	pos_x = 0
	width = epaper_size[0]
	cut = 10
	border = 4
	# if clock_text is provided, draw a full black box and center white text
	if clock_text is not None:
		image_draw.polygon((
			(pos_x, pos_y),
			(pos_x + (width - 2 * pos_x) - cut, pos_y),
			(pos_x + (width - 2 * pos_x), pos_y + cut),
			(pos_x + (width - 2 * pos_x), pos_y + height),
			(pos_x, pos_y + height)
			), fill=0)
		# center clock text
		font_to_use = font
		try:
			text_width = font_to_use.getlength(clock_text)
			text_x = (width - text_width) / 2
			# shift clock text slightly upward so it doesn't sit on the same horizontal band as the battery bar
			preferred_y = pos_y + (height - font_to_use.size) / 2 - 6
			# clamp so text stays inside the box
			text_y = max(pos_y + 2, preferred_y)
		except Exception:
			text_x = pos_x + 8
			text_y = pos_y + 4
		image_draw.text((text_x, text_y), clock_text, font=font_to_use, fill=255)
		return image_draw

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


def draw_clock_box(image_draw, pos_y, height, text, font_obj=None):
	"""Draw a full-black filled box (same shape as temp box) and center white text inside."""
	pos_x = 0
	width = epaper_size[0]
	cut = 10
	# draw outer filled polygon (completely black)
	image_draw.polygon((
		(pos_x, pos_y),
		(pos_x + (width - 2 * pos_x) - cut, pos_y),
		(pos_x + (width - 2 * pos_x), pos_y + cut),
		(pos_x + (width - 2 * pos_x), pos_y + height),
		(pos_x, pos_y + height)
		), fill=0)
	# center the text
	f = font_obj or font
	try:
		txt_w = f.getlength(text)
		tx = (width - txt_w) / 2
		ty = pos_y + (height - f.size) / 2
	except Exception:
		tx = 8
		ty = pos_y + 8
	image_draw.text((tx, ty), text, font=f, fill=255)
	return image_draw



def render_once():
	# Sample sensor data for four rooms. In real usage replace these with live readings.
	rooms = [
		{"name": "Living", "temp": 21.3, "hum": 45, "bat": 97},
		{"name": "Kitchen", "temp": 23.8, "hum": 50, "bat": 12},
		{"name": "Bedroom", "temp": 19.6, "hum": 55, "bat": 35},
		{"name": "Office", "temp": 20.1, "hum": 48, "bat": 67},
	]

	display_image = Image.new('1', epaper_size, 255)
	# rotation is a no-op for the image object; we keep orientation consistent with earlier code
	display_draw = ImageDraw.Draw(display_image)

	time_string = time.strftime('%H:%M')

	box_y = 0
	# First draw clock box with height 50
	clock_h = 50
	draw_box(display_draw, pos_y=box_y, height=clock_h, clock_text=time_string)
	# Draw four temp boxes below the clock box
	box_h = 45
	for i, r in enumerate(rooms):
		y = box_y + clock_h + 6 + i * (box_h + 4)
		draw_box(display_draw, pos_y=y, height=box_h, room_name=r['name'], temp_c=r['temp'], humidity=r['hum'], battery_level=r['bat'])

	# send to epaper
	try:
		if epaper is not None:
			epd.init()
		epd.display(epd.getbuffer(display_image))
		epd.sleep()
	except Exception:
		# Ensure dummy still tries to display
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
	try:
		while True:
			now = time.time()
			cur_min = time.strftime('%Y-%m-%d %H:%M', time.localtime(now))

			# get current sensor data (replace this with real data retrieval)
			rooms = [
				{"name": "Living", "temp": 21.3, "hum": 45, "bat": 97},
				{"name": "Kitchen", "temp": 23.8, "hum": 50, "bat": 12},
				{"name": "Bedroom", "temp": 19.6, "hum": 55, "bat": 35},
				{"name": "Office", "temp": 20.1, "hum": 48, "bat": 67},
			]

			if last_values['minute'] != cur_min:
				# minute changed -> full render
				full_image = Image.new('1', epaper_size, 255)
				full_drawer = ImageDraw.Draw(full_image)
				time_string = time.strftime('%H:%M')
				box_y = 0
				clock_h = 50
				draw_box(full_drawer, pos_y=box_y, height=clock_h, clock_text=time_string)
				box_h = 45
				for i, room in enumerate(rooms):
					y = box_y + clock_h + 6 + i * (box_h + 4)
					draw_box(full_drawer, pos_y=y, height=box_h, room_name=room['name'], temp_c=room['temp'], humidity=room['hum'], battery_level=room['bat'])

				# send full image
				try:
					if epaper is not None:
						epd.init()
					epd.display(epd.getbuffer(full_image))
					epd.sleep()
				except Exception:
					try:
						epd.display(epd.getbuffer(full_image))
						epd.sleep()
					except Exception:
						pass

				last_full_image = full_image.copy()
				last_values['minute'] = cur_min
				last_values['rooms'] = rooms
			else:
				# minute didn't change -> check for per-room changes and send partial updates
				for i, r in enumerate(rooms):
					prev = last_values['rooms'][i] if i < len(last_values['rooms']) else None
					changed = False
					if prev is None:
						changed = True
					else:
						# compare relevant fields (temp, hum, bat)
						if abs(prev.get('temp', 0) - r.get('temp', 0)) > 0.05:
							changed = True
						if prev.get('hum') != r.get('hum'):
							changed = True
						if prev.get('bat') != r.get('bat'):
							changed = True
					if changed:
						# compute box position
						box_y = 0
						clock_h = 50
						box_h = 45
						y = box_y + clock_h + 6 + i * (box_h + 4)
						# create a partial image the same size as full screen but only draw the affected box
						partial_image = Image.new('1', epaper_size, 255)
						partial_drawer = ImageDraw.Draw(partial_image)
						draw_box(partial_drawer, pos_y=y, height=box_h, room_name=r['name'], temp_c=r['temp'], humidity=r['hum'], battery_level=r['bat'])

						# try hardware partial update methods if available
						did_partial = False
						try:
							if hasattr(epd, 'display_partial'):
								try:
									epd.display_partial(epd.getbuffer(partial_image), x=0, y=y, w=epaper_size[0], h=box_h)
									did_partial = True
								except TypeError:
									# some drivers accept only buffer
									epd.display_partial(epd.getbuffer(partial_image))
									did_partial = True
							elif hasattr(epd, 'displayPartial'):
								epd.displayPartial(epd.getbuffer(partial_image))
								did_partial = True
						except Exception:
							did_partial = False

						if not did_partial:
							# fallback: composite onto last_full_image and send full buffer
							if last_full_image is None:
								last_full_image = Image.new('1', epaper_size, 255)
							try:
								last_full_image.paste(partial_image, (0, 0))
								epd.display(epd.getbuffer(last_full_image))
								epd.sleep()
							except Exception:
								try:
									epd.display(epd.getbuffer(partial_image))
									epd.sleep()
								except Exception:
									pass

						# update stored value
						if i < len(last_values['rooms']):
							last_values['rooms'][i] = r
						else:
							last_values['rooms'].append(r)

			time.sleep(poll_interval)
	except KeyboardInterrupt:
		try:
			epd.sleep()
		except Exception:
			pass
		print('Exiting')


if __name__ == '__main__':
	run_loop()


