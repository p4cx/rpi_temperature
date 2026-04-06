import argparse
import time

from data_sources import get_departures, get_inside_sensors, get_outside_weather
from display import build_image, save_preview, send


def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Render the e-paper temperature and MVV departure dashboard")
    parser.add_argument("--debug", action="store_true", help="Save the first generated image preview")
    parser.add_argument("--once", action="store_true", help="Render once and exit")
    return parser.parse_args(args)


def run_loop(debug=False):
    try:
        while True:
            departures = get_departures()
            weather = get_outside_weather()
            sensors = get_inside_sensors()
            image = build_image(departures, weather, sensors)
            if debug:
                save_preview(image)
                print("Debug mode: exiting after saving preview")
                break
            send(image)
            time.sleep(60)
    except KeyboardInterrupt:
        print("Exiting")


if __name__ == "__main__":
    run_loop(debug=False)

