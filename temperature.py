import argparse
import time

from data_sources import get_flight_data, get_inside_sensors, get_outside_weather
from display import build_image, save_preview, send


def parse_args():
    parser = argparse.ArgumentParser(description="Render the e-paper temperature and flight dashboard")
    parser.add_argument("--debug", action="store_true", help="Save the first generated image preview")
    parser.add_argument("--once", action="store_true", help="Render once and exit")
    return parser.parse_args()


def run_loop(debug=False, once=False):
    first_preview = True
    try:
        while True:
            flight = get_flight_data()
            weather = get_outside_weather()
            sensors = get_inside_sensors()
            image = build_image(flight, weather, sensors)
            if debug and first_preview:
                save_preview(image)
                first_preview = False
            send(image)
            if once:
                break
            time.sleep(60)
    except KeyboardInterrupt:
        print("Exiting")


if __name__ == "__main__":
    args = parse_args()
    run_loop(debug=args.debug, once=args.once)


