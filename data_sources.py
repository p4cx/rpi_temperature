import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

DEFAULT_LATITUDE = float(os.environ.get("OUTSIDE_LAT", "48.1"))
DEFAULT_LONGITUDE = float(os.environ.get("OUTSIDE_LON", "11.5"))
MVV_STATIONS_FILE = os.environ.get("MVV_STATIONS_FILE", "./mvv_stations.json")
MVV_DEPARTURES_COUNT = int(os.environ.get("MVV_DEPARTURES_COUNT", "10"))
MVV_DEPARTURES_PER_STATION = int(os.environ.get("MVV_DEPARTURES_PER_STATION", "10"))
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
MVV_DEPARTURES_URL = "https://www.mvg.de/api/bgw-pt/v3/departures?globalId="

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


def _shorten_destination(dest, max_chars=18):
    if not dest:
        return ""
    for sep in [" via ", " - ", " / ", " ("]:
        dest = dest.split(sep)[0]
    dest = dest.strip()
    if len(dest) <= max_chars:
        return dest
    words = dest.split()
    if len(words) > 1:
        head = " ".join(words[:2])
        if len(head) <= max_chars:
            return head + "…"
    return dest[: max_chars - 1].rstrip(" -") + "…"


def _format_departure(departure, station_name=None, station_priority=0):
    line = str(departure.get("label", "?")).strip()
    destination = _shorten_destination(departure.get("destination", ""), max_chars=18)
    planned = departure.get("plannedDepartureTime")
    realtime = departure.get("realtimeDepartureTime") or planned
    minutes = "??"
    sort_minutes = 999
    if isinstance(realtime, (int, float)):
        depart_dt = datetime.utcfromtimestamp(realtime / 1000)
        delta = int((depart_dt - datetime.utcnow()).total_seconds() / 60)
        sort_minutes = max(delta, 0)
        minutes = str(sort_minutes)
    payload = {
        "line": line,
        "destination": destination,
        "minutes": minutes,
        "sort_minutes": sort_minutes,
        "trip_id": departure.get("tripId") or departure.get("lineId") or f"{line}|{destination}",
        "station": station_name,
        "station_priority": station_priority,
    }
    return payload


def _load_mvv_stations():
    if os.path.exists(MVV_STATIONS_FILE):
        try:
            with open(MVV_STATIONS_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list) and data:
                stations = []
                for entry in data:
                    if isinstance(entry, dict) and entry.get("globalId"):
                        stations.append({
                            "name": entry.get("name", entry["globalId"]),
                            "globalId": entry["globalId"],
                            "priority": int(entry.get("priority", 0) or 0),
                        })
                    elif isinstance(entry, str):
                        stations.append({"name": entry, "globalId": entry, "priority": 0})
                if stations:
                    return stations
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Failed to load MVV station config {MVV_STATIONS_FILE}: {exc}")


def get_departures():
    stations = _load_mvv_stations()
    departures_map = {}

    for station in stations:
        station_id = station.get("globalId")
        if not station_id:
            continue

        station_name = station.get("name")
        station_priority = station.get("priority", 0)
        url = f"{MVV_DEPARTURES_URL}{urllib.parse.quote(station_id, safe=':/')}"
        station_departures = _fetch_json(url)
        if not isinstance(station_departures, list):
            continue

        for departure in station_departures[:MVV_DEPARTURES_PER_STATION]:
            formatted = _format_departure(
                departure,
                station_name=station_name,
                station_priority=station_priority,
            )
            trip_key = formatted["trip_id"]
            existing = departures_map.get(trip_key)
            if existing is None:
                departures_map[trip_key] = formatted
                continue

            if formatted["station_priority"] > existing["station_priority"]:
                departures_map[trip_key] = formatted
            elif (
                formatted["station_priority"] == existing["station_priority"]
                and formatted["sort_minutes"] < existing["sort_minutes"]
            ):
                departures_map[trip_key] = formatted

    departures = sorted(
        departures_map.values(),
        key=lambda item: (item.get("sort_minutes", 999), -item.get("station_priority", 0)),
    )[:MVV_DEPARTURES_COUNT]

    if not departures:
        return {"error": "MVV departures unavailable"}
    return {"departures": departures}


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
