import json
import os
import urllib.request
import urllib.error

DEFAULT_LATITUDE = float(os.environ.get("OUTSIDE_LAT", "48.114375"))
DEFAULT_LONGITUDE = float(os.environ.get("OUTSIDE_LON", "11.513758"))
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Heavy showers",
    82: "Violent showers",
}


def _fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "rpi-temperature/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        print(f"Failed to fetch JSON from {url}: {exc}")
        return None


def get_flight_data():
    url = os.environ.get("FLIGHT_DATA_URL")
    if not url:
        return {"error": "No FLIGHT_DATA_URL set"}

    payload = _fetch_json(url)
    if not isinstance(payload, dict):
        return {"error": "Flight data unavailable"}

    return {
        "flight_number": payload.get("flight_number") or payload.get("ident") or "N/A",
        "dep_city": payload.get("dep_city") or payload.get("departure_city") or "Depart",
        "dep_country": payload.get("dep_country") or payload.get("departure_country") or "",
        "arr_city": payload.get("arr_city") or payload.get("arrival_city") or "Arrive",
        "arr_country": payload.get("arr_country") or payload.get("arrival_country") or "",
    }


def get_outside_weather(latitude=DEFAULT_LATITUDE, longitude=DEFAULT_LONGITUDE):
    params = "latitude=%s&longitude=%s&current_weather=true&timezone=auto" % (latitude, longitude)
    url = f"{WEATHER_URL}?{params}"
    payload = _fetch_json(url)
    if not payload or not payload.get("current_weather"):
        return {"error": "Weather unavailable", "location": "Outside", "temperature": None, "condition": "N/A"}

    current = payload["current_weather"]
    return {
        "location": "Outside",
        "temperature": current.get("temperature"),
        "condition": WEATHER_CODES.get(current.get("weathercode"), "Unknown"),
    }


def get_inside_sensors():
    return [
        {"name": "Living", "temp": 21.3, "hum": 45, "bat": 87},
        {"name": "Kitchen", "temp": 23.8, "hum": 50, "bat": 73},
        {"name": "Bedroom", "temp": 19.6, "hum": 55, "bat": 61},
    ]
