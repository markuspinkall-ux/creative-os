"""Wetter über Open-Meteo (kostenlos, ohne Konto, ohne Schlüssel)."""

import json
import urllib.parse
import urllib.request

CODES = {
    0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bewölkt", 45: "neblig", 48: "neblig mit Reif",
    51: "leichter Nieselregen", 53: "Nieselregen", 55: "starker Nieselregen", 56: "gefrierender Nieselregen",
    57: "gefrierender Nieselregen", 61: "leichter Regen", 63: "Regen", 65: "starker Regen",
    66: "gefrierender Regen", 67: "gefrierender Regen", 71: "leichter Schneefall", 73: "Schneefall",
    75: "starker Schneefall", 77: "Schneegriesel", 80: "leichte Regenschauer", 81: "Regenschauer",
    82: "heftige Regenschauer", 85: "Schneeschauer", 86: "starke Schneeschauer", 95: "Gewitter",
    96: "Gewitter mit Hagel", 99: "schweres Gewitter mit Hagel",
}
DAY_NAMES = {0: "Heute", 1: "Morgen", 2: "Übermorgen"}


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "CreativeOS-Assistent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def locate(city):
    q = urllib.parse.urlencode({"name": city, "count": 1, "language": "de", "format": "json"})
    data = _get(f"https://geocoding-api.open-meteo.com/v1/search?{q}")
    res = (data.get("results") or [None])[0]
    if not res:
        return None
    return res["latitude"], res["longitude"], res.get("name", city)


def r(x):
    return int(round(x))


def report(city, day=0):
    """Gibt einen gesprochenen Satz zurück (oder wirft eine Ausnahme)."""
    place = locate(city)
    if not place:
        return f"Ich kenne den Ort {city} leider nicht."
    lat, lon, name = place
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 3,
        "current": "temperature_2m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    })
    data = _get(f"https://api.open-meteo.com/v1/forecast?{q}")
    d = data["daily"]
    text_day = CODES.get(d["weather_code"][day], "wechselhaft")
    tmin, tmax = r(d["temperature_2m_min"][day]), r(d["temperature_2m_max"][day])
    rain = d.get("precipitation_probability_max", [None] * 3)[day]
    if day == 0:
        cur = data["current"]
        sentence = (f"In {name} ist es gerade {r(cur['temperature_2m'])} Grad und "
                    f"{CODES.get(cur['weather_code'], 'wechselhaft')}. Heute {tmin} bis {tmax} Grad")
    else:
        sentence = f"{DAY_NAMES[day]} in {name}: {text_day}, {tmin} bis {tmax} Grad"
    if rain is not None and rain >= 30:
        sentence += f", Regenwahrscheinlichkeit {r(rain)} Prozent"
    return sentence + "."
