import os
import time

try:
    import epaper
except ImportError:
    epaper = None

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "./res/PixelOperator8.ttf"
EPAPER_SIZE = (122, 250)
CLOCK_HEIGHT = 42
BORDER = 4
GAP_AFTER_CLOCK = 3
FLIGHT_BOX_HEIGHT = 54
WEATHER_BOX_HEIGHT = 38
SENSOR_BOX_HEIGHT = 33
INTER_BOX_GAP = 3
PREVIEW_DIR = "./res/preview"


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)
    except Exception:
        return ImageFont.load_default()


def _text_size(text, font):
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


font = _load_font(FONT_PATH, 24)
small_font = _load_font(FONT_PATH, 8)

class DummyEPD:
    def init(self):
        print("DummyEPD.init()")

    def Clear(self, value):
        print(f"DummyEPD.Clear({value})")

    def display(self, buffer):
        os.makedirs(PREVIEW_DIR, exist_ok=True)
        image = buffer if isinstance(buffer, Image.Image) else _to_image(buffer)
        if image is None:
            print("DummyEPD.display() could not convert buffer")
            return

    def getbuffer(self, image):
        return image

    def sleep(self):
        print("DummyEPD.sleep()")


def _to_image(buffer):
    try:
        return Image.frombytes("1", EPAPER_SIZE, buffer)
    except Exception:
        return None


def init_epd():
    if epaper is None:
        return DummyEPD()

    ed = epaper.epaper("epd2in13_V4").EPD()
    ed.init()
    ed.Clear(0xFF)
    try:
        attrs = sorted(dir(ed))
        print("EPD attributes:\n" + "\n".join(attrs))
    except Exception as exc:
        print("Could not list epd attributes:", exc)
    return ed


epd = init_epd()


def _draw_box_border(draw, top, height, fill=0):
    width = EPAPER_SIZE[0]
    cut = 10
    outer = [(0, top), (width - cut, top), (width, top + cut), (width, top + height), (0, top + height)]
    draw.polygon(outer, fill=0)
    inner = [
        (BORDER, top + BORDER),
        (EPAPER_SIZE[0] - BORDER - cut + 2 , top + BORDER),
        (EPAPER_SIZE[0] - BORDER, top + cut + BORDER - 2),
        (EPAPER_SIZE[0] - BORDER, top + height - BORDER),
        (BORDER, top + height - BORDER),
    ]
    draw.polygon(inner, fill=fill)


def draw_clock_box(draw, top, height, clock_text, date_text):
    _draw_box_border(draw, top, height, fill=0)
    draw.text((0, top + 6), clock_text, font=font, fill=255)
    draw.text((BORDER + 2, top + 30), date_text, font=small_font, fill=255)


def draw_flight_box(draw, top, height, flight):
    _draw_box_border(draw, top, height, fill=255)
    if flight.get("error"):
        draw.text((BORDER + 2, top + 4), "FLIGHT ERROR", font=small_font, fill=0)
        draw.text((BORDER + 2, top + 18), flight["error"][:18], font=small_font, fill=0)
        return

    flight_number = flight.get("flight_number", "N/A")
    draw.text((BORDER + 2, top + 4), flight_number, font=small_font, fill=0)
    dep = flight.get("dep_city", "Depart")
    dep_country = flight.get("dep_country", "")
    arr = flight.get("arr_city", "Arrive")
    arr_country = flight.get("arr_country", "")
    draw.text((BORDER + 2, top + 18), f"{dep}, {dep_country}", font=small_font, fill=0)
    draw.text((BORDER + 2, top + 28), f"{arr}, {arr_country}", font=small_font, fill=0)


def draw_weather_box(draw, top, height, weather):
    _draw_box_border(draw, top, height, fill=255)
    if weather.get("error"):
        draw.text((BORDER + 2, top + 4), "WEATHER ERROR", font=small_font, fill=0)
        draw.text((BORDER + 2, top + 18), weather["error"][:18], font=small_font, fill=0)
        return

    location = weather.get("location", "Outside")
    temp = weather.get("temperature")
    condition = weather.get("condition", "---")
    draw.text((BORDER + 2, top + 4), location, font=small_font, fill=0)
    if temp is not None:
        temp_text = f"{temp:.1f}°C"
        text_w, _ = _text_size(temp_text, small_font)
        draw.text((EPAPER_SIZE[0] - BORDER - text_w - 2, top + 18), temp_text, font=small_font, fill=0)
    else:
        draw.text((BORDER + 2, top + 18), "N/A", font=small_font, fill=0)
    draw.text((BORDER + 2, top + 26), condition, font=small_font, fill=0)


def draw_sensor_box(draw, top, height, sensor):
    _draw_box_border(draw, top, height, fill=255)
    name = sensor.get("name", "?")
    temp = sensor.get("temp")
    hum = sensor.get("hum")
    bat = sensor.get("bat")
    draw.text((BORDER + 2, top + 4), name, font=small_font, fill=0)
    if temp is not None:
        draw.text((BORDER + 2, top + 16), f"{temp:.1f}°C", font=small_font, fill=0)
    if hum is not None:
        hum_text = f"{int(hum)}%"
        x = EPAPER_SIZE[0] - BORDER - _text_size(hum_text, small_font)[0] - 2
        draw.text((x, top + 16), hum_text, font=small_font, fill=0)
    if bat is not None:
        bar_top = top + 28
        bar_width = EPAPER_SIZE[0] - BORDER * 2
        fill_w = int(bar_width * max(0, min(100, float(bat))) / 100)
        draw.rectangle((BORDER, bar_top, BORDER + fill_w, bar_top + 4), fill=0)


def build_image(flight, weather, sensors):
    image = Image.new("1", EPAPER_SIZE, 255)
    drawer = ImageDraw.Draw(image)
    time_str = time.strftime("%H:%M")
    date_str = time.strftime("%a, %d.%m.%Y")
    draw_clock_box(drawer, 0, CLOCK_HEIGHT, time_str, date_str)
    top = CLOCK_HEIGHT + GAP_AFTER_CLOCK
    draw_flight_box(drawer, top, FLIGHT_BOX_HEIGHT, flight)
    top += FLIGHT_BOX_HEIGHT + INTER_BOX_GAP
    draw_weather_box(drawer, top, WEATHER_BOX_HEIGHT, weather)
    top += WEATHER_BOX_HEIGHT + INTER_BOX_GAP
    for sensor in sensors[:3]:
        draw_sensor_box(drawer, top, SENSOR_BOX_HEIGHT, sensor)
        top += SENSOR_BOX_HEIGHT + INTER_BOX_GAP
    return image


def save_preview(image, name="preview.png"):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    path = os.path.join(PREVIEW_DIR, name)
    image.convert("RGB").save(path)
    print(f"Saved preview: {path}")


def send(image):
    try:
        epd.display(epd.getbuffer(image))
        epd.sleep()
    except Exception:
        pass
