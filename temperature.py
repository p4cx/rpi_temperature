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

# Helper to send buffers to various epd driver signatures
def _send_to_epd(pil_image):
	"""Send a PIL image to the epd using the driver's available display API.
	Tries epd.display(black, red) then epd.display(buffer). Works with DummyEPD and
	Waveshare drivers that expect raw buffers.
	Returns True on success, False otherwise.
	"""
	try:
		buf = epd.getbuffer(pil_image)
	except Exception:
		print("_send_to_epd: epd.getbuffer failed")
		return False

	# If the driver returned a PIL image (DummyEPD), prefer sending that directly
	try:
		# Try two-argument display (black, red)
		try:
			# create a blank buffer only if buf is a bytes-like sequence
			if isinstance(buf, (bytes, bytearray)):
				blank = bytearray([0xFF]) * len(buf)
				print(f"_send_to_epd: using epd.display(buf, blank), buf_len={len(buf)}")
				epd.display(buf, blank)
			else:
				# assume driver will error on two args for PIL-backed DummyEPD
				print("_send_to_epd: using epd.display(buf, buf) with non-bytes buf")
				epd.display(buf, buf)
			return True
		except TypeError:
			# driver expects a single buffer or PIL image
			try:
				print("_send_to_epd: falling back to epd.display(buf)")
				epd.display(buf)
				return True
			except Exception as e:
				print("_send_to_epd: epd.display(buf) failed:", e)
				import traceback
				traceback.print_exc()
				# try to re-init the driver and try again once
				try:
					epd.init()
					print("_send_to_epd: epd.init() called after display failure, retrying display")
					epd.display(buf)
					return True
				except Exception as e2:
					print("_send_to_epd: retry epd.display after init failed:", e2)
					traceback.print_exc()
					# final fallback
					try:
						epd.display(pil_image)
						return True
					except Exception:
						return False
	except Exception:
		# final fallback: try single-arg display with the original pil_image
		try:
			epd.display(pil_image)
			return True
		except Exception:
			return False


def _send_partial(pil_image, x=0, y=0, w=None, h=None):
	"""Try to send only a region to the display using common driver partial APIs.
	If no partial API is available, fallback to sending the full image via _send_to_epd.
	"""
	try:
		if w is None:
			w = epaper_size[0]
		if h is None:
			h = epaper_size[1]

		# Prefer a low-level partial update using Waveshare methods if available
		# Ensure driver is initialized before attempting low-level partial calls
		try:
			epd.init()
			print("_send_partial: epd.init() called before partial")
		except Exception as ie:
			print("_send_partial: epd.init() failed:", ie)

		if (all(hasattr(epd, name) for name in ('SetWindow', 'SetCursor', 'send_data2', 'TurnOnDisplayPart'))
				or all(hasattr(epd, name) for name in ('set_windows', 'set_cursor', 'send_data2', 'ondisplay'))):
			try:
				# crop region from image to minimal buffer
				region = pil_image.crop((x, y, x + w, y + h)).convert('1')
				rw, rh = region.size
				# pad width to byte boundary
				line_bytes = (rw + 7) // 8
				if rw % 8 != 0:
					padded = Image.new('1', (line_bytes * 8, rh), 255)
					padded.paste(region, (0, 0))
					region = padded
					rw = region.size[0]
				buf = bytearray(region.tobytes())

				print(f"_send_partial: using low-level window API x={x} y={y} w={w} h={h} buf_len={len(buf)}")

				# call the appropriate window/set cursor functions depending on the driver
				try:
					if hasattr(epd, 'SetWindow') and hasattr(epd, 'SetCursor'):
						epd.SetWindow(x, y, x + w - 1, y + h - 1)
						epd.SetCursor(x, y)
					else:
						epd.set_windows(x, y, x + w - 1, y + h - 1)
						epd.set_cursor(x, y)

					# write black RAM (0x24) then data
					try:
						epd.send_command(0x24)
					except Exception:
						pass
					epd.send_data2(buf)

					# trigger a PARTIAL update using available method
					if hasattr(epd, 'TurnOnDisplayPart'):
						try:
							epd.TurnOnDisplayPart()
							if hasattr(epd, 'busy'):
								epd.busy()
							return True
						except Exception as e:
							print("_send_partial: TurnOnDisplayPart failed:", e)
					# try older ondisplay if present
					if hasattr(epd, 'ondisplay'):
						try:
							epd.ondisplay()
							return True
						except Exception as e:
							print("_send_partial: epd.ondisplay failed:", e)
					return True
				except Exception as e:
					import traceback
					print("_send_partial: low-level window API failed:", e)
					traceback.print_exc()
					# fallthrough to other partial APIs
					pass
			except Exception as e:
				import traceback
				print("_send_partial: low-level partial failed:", e)
				traceback.print_exc()
				# fallthrough to other partial APIs
				pass

		# driver-level convenience methods
		if hasattr(epd, 'display_partial'):
			try:
				print(f"_send_partial: using epd.display_partial x={x} y={y} w={w} h={h}")
				epd.display_partial(epd.getbuffer(pil_image), x=x, y=y, w=w, h=h)
				return True
			except TypeError:
				print("_send_partial: display_partial accepted only buffer")
				epd.display_partial(epd.getbuffer(pil_image))
				return True

		if hasattr(epd, 'displayPartial'):
			print("_send_partial: using epd.displayPartial")
			epd.displayPartial(epd.getbuffer(pil_image))
			return True
	except Exception as e:
		print("_send_partial: driver partial attempts raised:", e)
		# ignore and fallback
		pass

	# fallback to full send
	print("_send_partial: falling back to full send")
	return _send_to_epd(pil_image)

def draw_battery(draw, x, y, level, w=100, h=4):
	fill_pct = 0
	try:
		lvl = float(level)
		fill_pct = int(max(0, min(100, lvl)))
	except Exception:
		fill_pct = 0
	fill_w = int(w * (fill_pct / 100.0))
	if fill_w > 0:
		draw.rectangle((x, y + (h - (h))//2, x + fill_w, y + h - (h)//2), outline=0, fill=0)


def draw_box(image_draw, pos_y, height, room_name=None, temp_c=None, humidity=None, battery_level=0, clock_text=None):
	"""Draw a single box at vertical position pos_y with given height.
	If clock_text is provided, draw a black clock box with centered white text.
	Otherwise draw a framed box (black outer, white inner) and render room letter, battery bar,
	temperature (left) and humidity (bottom/right).
	"""
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
		draw_battery(image_draw, bx, by, battery_level, w=bar_w, h=bar_h)

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
		if epaper is not None:
			epd.init()
		_send_to_epd(display_image)
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
				# minute changed -> do minimal partial updates: clock + only changed room boxes
				# If we don't have a last_full_image yet, render and send it fully once
				if last_full_image is None:
					full_image = Image.new('1', epaper_size, 255)
					full_drawer = ImageDraw.Draw(full_image)
					time_string = time.strftime('%H:%M')
					box_y = 0
					draw_box(full_drawer, pos_y=box_y, height=CLOCK_HEIGHT, clock_text=time_string)
					for i, room in enumerate(rooms):
						y = box_y + CLOCK_HEIGHT + GAP_AFTER_CLOCK + i * (BOX_HEIGHT + INTER_BOX_GAP)
						draw_box(full_drawer, pos_y=y, height=BOX_HEIGHT, room_name=room['name'], temp_c=room['temp'], humidity=room['hum'], battery_level=room['bat'])
					# send full image once (initialization)
					try:
						if epaper is not None:
							epd.init()
							_send_to_epd(full_image)
							epd.sleep()
					except Exception:
						try:
							_send_to_epd(full_image)
							epd.sleep()
						except Exception:
							pass
					last_full_image = full_image.copy()
					last_values['minute'] = cur_min
					last_values['rooms'] = rooms
					partial_update_counter = 0
				else:
					# partial-update the clock area
					try:
						box_y = 0
						clock_partial = Image.new('1', epaper_size, 255)
						clock_draw = ImageDraw.Draw(clock_partial)
						time_string = time.strftime('%H:%M')
						draw_box(clock_draw, pos_y=box_y, height=CLOCK_HEIGHT, clock_text=time_string)
						sent = _send_partial(clock_partial, x=0, y=box_y, w=epaper_size[0], h=CLOCK_HEIGHT)
						# always update stored full image so our state stays consistent
						if last_full_image is None:
							last_full_image = Image.new('1', epaper_size, 255)
							# paste only non-white pixels so we don't erase existing content on failed/partial updates
							mask = clock_partial.convert('L').point(lambda p: 255 - p)
							last_full_image.paste(clock_partial, (0, 0), mask)
						if sent:
							partial_update_counter += 1
					except Exception:
						pass
					# partial-update only rooms that changed
					for i, room in enumerate(rooms):
						prev = last_values['rooms'][i] if i < len(last_values['rooms']) else None
						room_changed = False
						if prev is None:
							room_changed = True
						else:
							if abs(prev.get('temp', 0) - room.get('temp', 0)) > 0.05:
								room_changed = True
							if prev.get('hum') != room.get('hum'):
								room_changed = True
							if prev.get('bat') != room.get('bat'):
								room_changed = True
						if room_changed:
							try:
								box_y = 0
								y = box_y + CLOCK_HEIGHT + GAP_AFTER_CLOCK + i * (BOX_HEIGHT + INTER_BOX_GAP)
								partial_image = Image.new('1', epaper_size, 255)
								partial_drawer = ImageDraw.Draw(partial_image)
								draw_box(partial_drawer, pos_y=y, height=BOX_HEIGHT, room_name=room['name'], temp_c=room['temp'], humidity=room['hum'], battery_level=room['bat'])
								sent = _send_partial(partial_image, x=0, y=y, w=epaper_size[0], h=BOX_HEIGHT)
								# always update stored full image
								if last_full_image is None:
									last_full_image = Image.new('1', epaper_size, 255)
								# paste only non-white pixels to avoid wiping existing display state
								mask = partial_image.convert('L').point(lambda p: 255 - p)
								last_full_image.paste(partial_image, (0, 0), mask)
								if sent:
									partial_update_counter += 1
							except Exception:
								pass
					# update stored values
					last_values['minute'] = cur_min
					last_values['rooms'] = rooms
					# after doing the minute-change partial updates, reset the partial counter
					# so we don't trigger a full refresh immediately
					partial_update_counter = 0
			else:
				# minute didn't change -> check for per-room changes and send partial updates
				# also attempt to update the clock area partially
				try:
					# create a partial image containing only the clock box
					clock_partial = Image.new('1', epaper_size, 255)
					clock_draw = ImageDraw.Draw(clock_partial)
					box_y = 0
					draw_box(clock_draw, pos_y=box_y, height=CLOCK_HEIGHT, clock_text=time.strftime('%H:%M'))
					did_clock_partial = False
					if hasattr(epd, 'display_partial'):
						try:
							epd.display_partial(epd.getbuffer(clock_partial), x=0, y=box_y, w=epaper_size[0], h=CLOCK_HEIGHT)
							did_clock_partial = True
						except TypeError:
							epd.display_partial(epd.getbuffer(clock_partial))
							did_clock_partial = True
					elif hasattr(epd, 'displayPartial'):
						epd.displayPartial(epd.getbuffer(clock_partial))
						did_clock_partial = True
					if did_clock_partial:
						partial_update_counter += 1
				except Exception:
					# ignore partial clock failures and continue
					pass
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
						y = box_y + CLOCK_HEIGHT + GAP_AFTER_CLOCK + i * (BOX_HEIGHT + INTER_BOX_GAP)
						# create a partial image the same size as full screen but only draw the affected box
						partial_image = Image.new('1', epaper_size, 255)
						partial_drawer = ImageDraw.Draw(partial_image)
						draw_box(partial_drawer, pos_y=y, height=BOX_HEIGHT, room_name=r['name'], temp_c=r['temp'], humidity=r['hum'], battery_level=r['bat'])

						# try hardware partial update methods if available
						did_partial = False
						try:
							if hasattr(epd, 'display_partial'):
								try:
									epd.display_partial(epd.getbuffer(partial_image), x=0, y=y, w=epaper_size[0], h=BOX_HEIGHT)
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
								_send_to_epd(last_full_image)
								epd.sleep()
								# count this as a partial update (we displayed a composite)
								partial_update_counter += 1
							except Exception:
								try:
									epd.init()
									_send_to_epd(partial_image)
									epd.sleep()
									# even this fallback counts as a partial attempt
									partial_update_counter += 1
								except Exception:
									pass

						# update stored value
						if i < len(last_values['rooms']):
							last_values['rooms'][i] = r
						else:
							last_values['rooms'].append(r)

			# if we've reached the partial-update threshold, force a full refresh
			if partial_update_counter >= FULL_UPDATE_AFTER_PARTIALS:
				try:
					full_image = Image.new('1', epaper_size, 255)
					full_drawer = ImageDraw.Draw(full_image)
					time_string = time.strftime('%H:%M')
					box_y = 0
					draw_box(full_drawer, pos_y=box_y, height=CLOCK_HEIGHT, clock_text=time_string)
					for i, room in enumerate(rooms):
						y = box_y + CLOCK_HEIGHT + GAP_AFTER_CLOCK + i * (BOX_HEIGHT + INTER_BOX_GAP)
						draw_box(full_drawer, pos_y=y, height=BOX_HEIGHT, room_name=room['name'], temp_c=room['temp'], humidity=room['hum'], battery_level=room['bat'])
					if epaper is not None:
						epd.init()
						_send_to_epd(full_image)
						epd.sleep()
				except Exception:
					try:
						epd.display(epd.getbuffer(full_image))
						epd.sleep()
					except Exception:
						pass
				# update stored state and reset counter
				last_full_image = full_image.copy()
				last_values['rooms'] = rooms
				partial_update_counter = 0

			time.sleep(poll_interval)
	except KeyboardInterrupt:
		try:
			epd.sleep()
		except Exception:
			pass
		print('Exiting')


if __name__ == '__main__':
	run_loop()


