"""Weather lookup.

Works out of the box using the free wttr.in service (no key needed).
If you set the OPENWEATHER_API_KEY environment variable, OpenWeatherMap is used instead.
"""
import os
from urllib.parse import quote

import requests

import config


class WeatherError(Exception):
    """Raised with a message that is safe to speak aloud."""


def _openweather(city, key):
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": key, "units": "metric"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise WeatherError("I couldn't reach the weather service. Please check your internet connection.") from exc
    if r.status_code == 404:
        raise WeatherError(f"I couldn't find a city called {city}.")
    if r.status_code == 401:
        raise WeatherError("The OpenWeather API key was rejected. Please check it.")
    if r.status_code != 200:
        raise WeatherError("The weather service is not responding right now.")
    d = r.json()
    return {
        "city": d.get("name") or city,
        "temp": round(d["main"]["temp"]),
        "feels": round(d["main"]["feels_like"]),
        "humidity": d["main"]["humidity"],
        "desc": d["weather"][0]["description"],
    }


def _wttr(city):
    try:
        r = requests.get(
            f"https://wttr.in/{quote(city)}",
            params={"format": "j1"},
            headers={"User-Agent": "jarvis-assistant"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise WeatherError("I couldn't reach the weather service. Please check your internet connection.") from exc
    if r.status_code == 404:
        raise WeatherError(f"I couldn't find a city called {city}.")
    if r.status_code != 200:
        raise WeatherError("The weather service is not responding right now.")
    try:
        cur = r.json()["current_condition"][0]
        return {
            "city": city,
            "temp": int(cur["temp_C"]),
            "feels": int(cur["FeelsLikeC"]),
            "humidity": int(cur["humidity"]),
            "desc": cur["weatherDesc"][0]["value"].lower(),
        }
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise WeatherError(f"I couldn't find weather details for {city}.") from exc


def get_weather(city=None):
    """Return a sentence describing the current weather in `city`."""
    city = (city or config.DEFAULT_CITY).strip()
    key = os.environ.get("OPENWEATHER_API_KEY", "").strip()
    w = _openweather(city, key) if key else _wttr(city)
    return (
        f"Right now in {w['city']} it is {w['temp']} degrees Celsius with {w['desc']}. "
        f"It feels like {w['feels']} degrees, and the humidity is {w['humidity']} percent."
    )
