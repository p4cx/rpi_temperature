import os
import time

try:
    import epaper
except ImportError:
    epaper = None

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "./res/PixelOperator8.ttf"
EPAPER_SIZE = (122, 250)
BORDER = 4
INTER_BOX_GAP = 4
CLOCK_HEIGHT = 42
DEPARTURE_BOX_HEIGHT = 102
CUT_CORNER = 6
DEPARTURE_ROWS = 9
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


def _draw_box_border(draw, left, top, width, height, fill=0, cut=6):
    right = left + width
    outer = [(left, top), (right - cut, top), (right, top + cut), (right, top + height), (left, top + height)]
    draw.polygon(outer, fill=0)
    inner = [
        (left + BORDER, top + BORDER),
        (right - BORDER - cut + 2, top + BORDER),
        (right - BORDER, top + cut + BORDER - 2),
        (right - BORDER, top + height - BORDER),
        (left + BORDER, top + height - BORDER),
    ]
    draw.polygon(inner, fill=fill)


def draw_clock_box(draw, top, height, clock_text, date_text):
    _draw_box_border(draw, 0, top, EPAPER_SIZE[0], height, fill=0)
    draw.text((BORDER, top + 6), clock_text, font=font, fill=255)
    draw.text((BORDER + 2, top + 30), date_text, font=small_font, fill=255)

station_abbreviations = {
    "Münchner": "Mü.",
    "Klinikum": "Kli.",
    "platz": "pl.",
    "straße": "str."
}

def draw_departure_box(draw, top, height, departures_data):
    _draw_box_border(draw, 0, top, EPAPER_SIZE[0], height, fill=255)
    if departures_data.get("error"):
        draw.text((BORDER + 2, top + 8), "MVV ERROR", font=small_font, fill=0)
        draw.text((BORDER + 2, top + 18), departures_data["error"][:18], font=small_font, fill=0)
        return
    
    departures = departures_data.get("departures", [])
    if not departures:
        draw.text((BORDER + 2, top + 8), "No departures", font=small_font, fill=0)
        return

    rows = DEPARTURE_ROWS
    row_height = 10
    for idx, departure in enumerate(departures[:rows]):
        row_top = top + BORDER * 2 + idx * row_height
        line = departure.get("line", "?")
        destination = departure.get("destination", "")
        for _old, _new in station_abbreviations.items():
            destination = destination.replace(_old, _new)
        minutes = departure.get("minutes", "")
        label_text = f"{line} {destination}".strip()
        if int(minutes) >= 10:
            max_width = EPAPER_SIZE[0] - BORDER * 2 - 20
        else:
            max_width = EPAPER_SIZE[0] - BORDER * 2 - 12
        if _text_size(label_text, small_font)[0] > max_width:
            while label_text and _text_size(label_text + "…", small_font)[0] > max_width:
                label_text = label_text[:-1]
            label_text = label_text.rstrip() + "…"
        draw.text((BORDER + 2, row_top), label_text, font=small_font, fill=0)
        if minutes:
            time_w, _ = _text_size(minutes, small_font)
            draw.text((EPAPER_SIZE[0] - BORDER - time_w - 1, row_top), minutes, font=small_font, fill=0)


def draw_temp_box(draw, left, top, width, height, data):
    _draw_box_border(draw, left, top, width, height, fill=255)
    temp = data.get("temperature", data.get("temp"))
    if temp is not None:
        temp_text = f"{temp:.1f}°C"
        text_w, _ = _text_size(temp_text, small_font)
        draw.text((left + (width - text_w) // 2, top + 6), temp_text, font=small_font, fill=0)
    else:
        draw.text((left + BORDER + 2, top + 6), "No data", font=small_font, fill=0)

    bottom_text = data.get("condition")
    if bottom_text is None and "hum" in data and data["hum"] is not None:
        bottom_text = f"{int(data['hum'])}%"

    if bottom_text:
        draw.text((left + BORDER + 2, top + height - 14), bottom_text[: max(0, width // 6)], font=small_font, fill=0)

    bat = data.get("bat")
    if bat is not None:
        draw.text((left + BORDER + 100, top + height - 14), f"{float(bat):.1f}%", font=small_font, fill=0)


def build_image(departures_data, weather, sensors):
    image = Image.new("1", EPAPER_SIZE, 255)
    drawer = ImageDraw.Draw(image)
    time_str = time.strftime("%H:%M")
    date_str = time.strftime("%a, %d.%m.%Y")
    draw_clock_box(drawer, 0, CLOCK_HEIGHT, time_str, date_str)
    top = CLOCK_HEIGHT + INTER_BOX_GAP
    draw_departure_box(drawer, top, DEPARTURE_BOX_HEIGHT, departures_data)
    top += DEPARTURE_BOX_HEIGHT + INTER_BOX_GAP

    draw_temp_box(drawer, 0, top, EPAPER_SIZE[0], 28, weather)
    top += 28 + INTER_BOX_GAP
    draw_temp_box(drawer, 0, top, EPAPER_SIZE[0], 20, sensors[0])
    top += 20 + INTER_BOX_GAP
    draw_temp_box(drawer, 0, top, EPAPER_SIZE[0], 20, sensors[1])
    top += 20 + INTER_BOX_GAP
    draw_temp_box(drawer, 0, top, EPAPER_SIZE[0], 20, sensors[2])

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
