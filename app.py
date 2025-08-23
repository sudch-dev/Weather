import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List

import pytz
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# -------------------- Config --------------------
IST = pytz.timezone("Asia/Kolkata")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")
# Durgapur, West Bengal (fixed as requested)
FIXED_COORDS = (23.5204, 87.3119, "Durgapur", "West Bengal")

# -------------------- Weathercode → Description --------------------
WEATHERCODE_DESC = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm (slight or moderate)",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# -------------------- Helpers --------------------
def weather_desc(code: int) -> str:
    return WEATHERCODE_DESC.get(code, "Unknown")

def parse_to_ist(iso_str: str) -> str:
    """Convert Open-Meteo 'YYYY-MM-DDTHH:MM' strings (assumed UTC) to IST string."""
    if not iso_str:
        return "N/A"
    try:
        dt_utc = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M")
        dt_utc = pytz.utc.localize(dt_utc)
        dt_ist = dt_utc.astimezone(IST)
        return dt_ist.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str

def get_ip_location():
    # Fixed location, as requested
    return FIXED_COORDS  # (lat, lon, city, region)

def build_forecast_url(lat: float, lon: float) -> str:
    hourly_vars = [
        "temperature_2m",
        "apparent_temperature",
        "relative_humidity_2m",
        "dew_point_2m",
        "precipitation",
        "rain",
        "showers",
        "snowfall",
        "snow_depth",
        "precipitation_probability",
        "pressure_msl",
        "surface_pressure",
        "cloud_cover",
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "visibility",
        "uv_index",
        "uv_index_clear_sky",
        "wind_speed_10m",
        "wind_gusts_10m",
        "wind_direction_10m",
    ]
    daily_vars = [
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "sunrise",
        "sunset",
        "uv_index_max",
        "uv_index_clear_sky_max",
        "precipitation_sum",
        "rain_sum",
        "showers_sum",
        "snowfall_sum",
        "precipitation_hours",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "wind_direction_10m_dominant",
    ]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&hourly={','.join(hourly_vars)}"
        f"&daily={','.join(daily_vars)}"
        "&timeformat=iso"
        "&timezone=auto"
    )
    return url

def build_air_quality_url(lat: float, lon: float) -> str:
    aq_hourly = [
        "pm10",
        "pm2_5",
        "carbon_monoxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
        "aerosol_optical_depth",
        "dust",
        "uv_index",
        "uv_index_clear_sky",
        "alder_pollen",
        "birch_pollen",
        "grass_pollen",
        "mugwort_pollen",
        "olive_pollen",
        "ragweed_pollen",
        "european_aqi",
        "european_aqi_pm2_5",
        "european_aqi_pm10",
        "european_aqi_no2",
        "european_aqi_o3",
        "european_aqi_so2",
        "us_aqi",
        "us_aqi_pm2_5",
        "us_aqi_pm10",
        "us_aqi_no2",
        "us_aqi_o3",
        "us_aqi_so2",
        "us_aqi_co",
    ]
    return (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly={','.join(aq_hourly)}"
        "&timeformat=iso"
        "&timezone=auto"
    )

def fetch_json(url: str) -> Dict[str, Any]:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e), "_url": url}

def assemble_payload(lat: float, lon: float) -> Dict[str, Any]:
    forecast_url = build_forecast_url(lat, lon)
    air_url = build_air_quality_url(lat, lon)
    forecast = fetch_json(forecast_url)
    air = fetch_json(air_url)

    # Normalize current weather (add description + IST time)
    current = forecast.get("current_weather", {}) if isinstance(forecast, dict) else {}
    current_out = {
        "temperature": current.get("temperature"),
        "windspeed": current.get("windspeed"),
        "winddirection": current.get("winddirection"),
        "weathercode": current.get("weathercode"),
        "weather_desc": weather_desc(current.get("weathercode", -1)),
        "time_ist": parse_to_ist(current.get("time", "")),
    }

    # Prepare hourly as list of dicts (only first 24 for page brevity)
    hourly = forecast.get("hourly", {})
    hourly_times: List[str] = hourly.get("time", [])[:24]
    hourly_out: List[Dict[str, Any]] = []
    for i, t in enumerate(hourly_times):
        entry = {"time_ist": parse_to_ist(t)}
        for k, v in hourly.items():
            if k == "time":
                continue
            try:
                entry[k] = v[i]
            except Exception:
                entry[k] = None
        hourly_out.append(entry)

    # Daily (next 7 days)
    daily = forecast.get("daily", {})
    daily_times: List[str] = daily.get("time", [])[:7]
    daily_out: List[Dict[str, Any]] = []
    for i, d in enumerate(daily_times):
        entry = {"date": d}
        for k, v in daily.items():
            if k == "time":
                continue
            try:
                entry[k] = v[i]
            except Exception:
                entry[k] = None
        # enrich with description if weathercode present (some daily payloads include a code)
        code = entry.get("weathercode")
        if code is not None:
            entry["weather_desc"] = weather_desc(code)
        # sunrise/sunset to IST
        if entry.get("sunrise"):
            entry["sunrise_ist"] = parse_to_ist(entry["sunrise"])
        if entry.get("sunset"):
            entry["sunset_ist"] = parse_to_ist(entry["sunset"])
        daily_out.append(entry)

    # Air Quality hourly (first 24)
    aq_hourly = air.get("hourly", {}) if isinstance(air, dict) else {}
    aq_times: List[str] = aq_hourly.get("time", [])[:24]
    aq_out: List[Dict[str, Any]] = []
    for i, t in enumerate(aq_times):
        entry = {"time_ist": parse_to_ist(t)}
        for k, v in aq_hourly.items():
            if k == "time":
                continue
            try:
                entry[k] = v[i]
            except Exception:
                entry[k] = None
        aq_out.append(entry)

    return {
        "meta": {
            "forecast_url": forecast_url,
            "air_quality_url": air_url,
            "timezone": forecast.get("timezone", "auto"),
            "elevation": forecast.get("elevation"),
            "generationtime_ms": forecast.get("generationtime_ms"),
        },
        "current": current_out,
        "hourly": hourly_out,
        "daily": daily_out,
        "air_quality": aq_out,
        "errors": {
            "forecast": forecast.get("_error"),
            "air": air.get("_error"),
        },
    }

# -------------------- Routes --------------------
@app.route("/")
def index():
    lat, lon, city, region = get_ip_location()
    payload = assemble_payload(lat, lon)
    now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        "index.html",
        city=city,
        region=region,
        now_ist=now_ist,
        payload=payload,
    )

@app.route("/ping")
def ping():
    return "pong"

def ping_self_forever():
    """Keep-alive thread that periodically pings this app's /ping route."""
    url = os.environ.get("APP_BASE_URL", APP_BASE_URL).rstrip("/") + "/ping"
    while True:
        try:
            time.sleep(600)  # every 10 minutes
            requests.get(url, timeout=10)
            # Optional: print to logs
            print(f"[KEEPALIVE] Pinged {url}")
        except Exception as e:
            print(f"[KEEPALIVE] Ping failed: {e}")

@app.route("/start")
def start():
    """Start the keep-alive thread (idempotent)."""
    if not getattr(app, "_keepalive_started", False):
        t = threading.Thread(target=ping_self_forever, daemon=True)
        t.start()
        app._keepalive_started = True
        return "Keep-alive thread started."
    return "Keep-alive already running."

# (Optional) auto-start keepalive on first request
@app.before_request
def ensure_keepalive():
    if not getattr(app, "_keepalive_started", False):
        try:
            t = threading.Thread(target=ping_self_forever, daemon=True)
            t.start()
            app._keepalive_started = True
        except Exception:
            pass

if __name__ == "__main__":
    # For local dev:
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
