import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

import pytz
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# -------------------- Config --------------------
IST = pytz.timezone("Asia/Kolkata")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")

# Quick toggles
DURGAPUR = (23.5204, 87.3119, "Durgapur", "West Bengal")
KOLKATA  = (22.5726, 88.3639, "Kolkata",  "West Bengal")

# -------------------- Weathercode → Description --------------------
WEATHERCODE_DESC = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
    82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm (slight or moderate)", 96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

def weather_desc(code: Any) -> str:
    try:
        return WEATHERCODE_DESC.get(int(code), "Unknown")
    except Exception:
        return "Unknown"

def parse_to_ist(iso_str: str) -> str:
    if not iso_str:
        return "N/A"
    try:
        dt_utc = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M")
        dt_utc = pytz.utc.localize(dt_utc)
        dt_ist = dt_utc.astimezone(IST)
        return dt_ist.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str

def _join(items: List[str]) -> str:
    return ",".join(items)

def _safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def build_forecast_url(lat: float, lon: float) -> str:
    hourly = [
        "temperature_2m","apparent_temperature","relative_humidity_2m","dew_point_2m",
        "precipitation","rain","showers","snowfall","snow_depth","precipitation_probability",
        "pressure_msl","surface_pressure","cloud_cover","cloud_cover_low","cloud_cover_mid","cloud_cover_high",
        "visibility","uv_index","uv_index_clear_sky",
        "wind_speed_10m","wind_gusts_10m","wind_direction_10m",
    ]
    daily = [
        "temperature_2m_max","temperature_2m_min","apparent_temperature_max","apparent_temperature_min",
        "sunrise","sunset","uv_index_max","uv_index_clear_sky_max",
        "precipitation_sum","rain_sum","showers_sum","snowfall_sum","precipitation_hours",
        "wind_speed_10m_max","wind_gusts_10m_max","wind_direction_10m_dominant",
    ]
    return (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&hourly={_join(hourly)}"
        f"&daily={_join(daily)}"
        "&timeformat=iso8601"
        "&timezone=UTC"
        "&past_days=0"
        "&forecast_days=8"     # 👈 ensure the coming week is present
    )

def build_air_quality_url(lat: float, lon: float) -> str:
    aq_hourly = [
        "pm10","pm2_5","carbon_monoxide","nitrogen_dioxide","sulphur_dioxide","ozone",
        "aerosol_optical_depth","dust","uv_index","uv_index_clear_sky",
        "alder_pollen","birch_pollen","grass_pollen","mugwort_pollen","olive_pollen","ragweed_pollen",
        "european_aqi","european_aqi_pm2_5","european_aqi_pm10","european_aqi_no2","european_aqi_o3","european_aqi_so2",
        "us_aqi","us_aqi_pm2_5","us_aqi_pm10","us_aqi_no2","us_aqi_o3","us_aqi_so2","us_aqi_co",
    ]
    return (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly={_join(aq_hourly)}"
        "&timeformat=iso8601"
        "&timezone=UTC"
    )

def fetch_json(url: str) -> Dict[str, Any]:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

def pick_location_from_query() -> Tuple[float, float, str, str]:
    q_lat = request.args.get("lat")
    q_lon = request.args.get("lon")
    if q_lat and q_lon:
        name = request.args.get("name", "Custom")
        region = request.args.get("region", "")
        try:
            return (float(q_lat), float(q_lon), name, region)
        except Exception:
            pass
    city = (request.args.get("city") or "").strip().lower()
    if city == "kolkata":
        return KOLKATA
    return DURGAPUR

def _closest_index_to_now(iso_times: List[str]) -> Optional[int]:
    if not iso_times:
        return None
    try:
        now_utc = datetime.utcnow()
        best_i, best_diff = 0, float("inf")
        for i, ts in enumerate(iso_times):
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M")
            diff = abs((dt - now_utc).total_seconds())
            if diff < best_diff:
                best_i, best_diff = i, diff
        return best_i
    except Exception:
        return None

def assemble_payload(lat: float, lon: float) -> Dict[str, Any]:
    forecast = fetch_json(build_forecast_url(lat, lon))
    air      = fetch_json(build_air_quality_url(lat, lon))

    # -------- Meta --------
    meta = {
        "forecast_url": build_forecast_url(lat, lon),
        "air_quality_url": build_air_quality_url(lat, lon),
        "timezone": forecast.get("timezone", "UTC"),
        "elevation": forecast.get("elevation"),
        "generationtime_ms": _safe_float(forecast.get("generationtime_ms"), 0.0),
    }

    # -------- Current --------
    cur = forecast.get("current_weather", {}) if isinstance(forecast, dict) else {}
    current = {
        "temperature": cur.get("temperature"),
        "windspeed": cur.get("windspeed"),
        "winddirection": cur.get("winddirection"),
        "weathercode": cur.get("weathercode"),
        "weather_desc": weather_desc(cur.get("weathercode")),
        "time_ist": parse_to_ist(cur.get("time", "")),
    }

    # -------- Hourly (send ALL hours so UI can filter safely) --------
    hourly = forecast.get("hourly", {}) if isinstance(forecast, dict) else {}
    times_h = list(hourly.get("time", []))
    hourly_out: List[Dict[str, Any]] = []
    for i, t in enumerate(times_h):     # 👈 no slicing
        row = {"time_ist": parse_to_ist(t), "time_utc": t}
        for key, series in hourly.items():
            if key == "time":
                continue
            try:
                row[key] = series[i]
            except Exception:
                row[key] = None
        hourly_out.append(row)

    # -------- Daily (7) --------
    daily = forecast.get("daily", {}) if isinstance(forecast, dict) else {}
    times_d = list(daily.get("time", []))[:7]
    daily_out: List[Dict[str, Any]] = []
    for i, d in enumerate(times_d):
        row = {"date": d}
        for key, series in daily.items():
            if key == "time":
                continue
            try:
                row[key] = series[i]
            except Exception:
                row[key] = None
        if row.get("weathercode") is not None:
            row["weather_desc"] = weather_desc(row.get("weathercode"))
        if row.get("sunrise"):
            row["sunrise_ist"] = parse_to_ist(row["sunrise"])
        if row.get("sunset"):
            row["sunset_ist"] = parse_to_ist(row["sunset"])
        daily_out.append(row)

    # -------- Today (alerts) --------
    precip_prob = None
    i_near = _closest_index_to_now(times_h)
    if i_near is not None:
        try:
            pp_list = hourly.get("precipitation_probability")
            if pp_list:
                precip_prob = pp_list[i_near]
        except Exception:
            precip_prob = None

    temp_now = current.get("temperature")
    precip_alert = (precip_prob is not None) and (precip_prob >= 85)
    temp_alert = (temp_now is not None) and (temp_now >= 35 or temp_now <= 10)

    today = {
        "temperature": temp_now,
        "precip_prob": precip_prob,
        "alert": bool(precip_alert or temp_alert),
        "temp_alert": bool(temp_alert),
        "precip_alert": bool(precip_alert),
    }

    # -------- Air Quality (24) --------
    aq = air.get("hourly", {}) if isinstance(air, dict) else {}
    aq_times = list(aq.get("time", []))[:24]
    aq_out: List[Dict[str, Any]] = []
    for i, t in enumerate(aq_times):
        row = {"time_ist": parse_to_ist(t)}
        for key, series in aq.items():
            if key == "time":
                continue
            try:
                row[key] = series[i]
            except Exception:
                row[key] = None
        aq_out.append(row)

    return {
        "meta": meta,
        "current": current,
        "hourly": hourly_out,
        "daily": daily_out,
        "air_quality": aq_out,
        "today": today,
        "errors": {"forecast": forecast.get("_error"), "air": air.get("_error")},
    }

# -------------------- Keep Alive --------------------
@app.route("/ping")
def ping():
    return "pong"

def _keepalive():
    url = APP_BASE_URL.rstrip("/") + "/ping"
    while True:
        try:
            time.sleep(600)
            requests.get(url, timeout=10)
            print(f"[KEEPALIVE] Pinged {url}")
        except Exception as e:
            print(f"[KEEPALIVE] Ping failed: {e}")

@app.before_request
def ensure_keepalive():
    if not getattr(app, "_ka_started", False):
        t = threading.Thread(target=_keepalive, daemon=True)
        t.start()
        app._ka_started = True

@app.route("/start")
def start_keepalive():
    if getattr(app, "_ka_started", False):
        return "Keep-alive already running."
    ensure_keepalive()
    return "Keep-alive started."

# -------------------- Geocoding (typeahead) --------------------
@app.get("/geo")
def geo_search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 3:
        return jsonify({"results": []})
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=6&language=en&format=json"
    data = fetch_json(url)
    results = []
    for r in data.get("results", []) or []:
        results.append({
            "name": r.get("name"),
            "admin1": r.get("admin1"),
            "country": r.get("country"),
            "lat": r.get("latitude"),
            "lon": r.get("longitude"),
        })
    return jsonify({"results": results})

# -------------------- Main route --------------------
@app.route("/")
def index():
    lat, lon, city, region = pick_location_from_query()
    payload = assemble_payload(lat, lon)
    now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        "index.html",
        city=city, region=region, now_ist=now_ist,
        lat=lat, lon=lon,
        payload=payload
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
