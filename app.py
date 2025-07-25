from flask import Flask, render_template
import requests
from datetime import datetime
import pytz
import threading
import time

app = Flask(__name__)

# Fixed coordinates for Durgapur, West Bengal
def get_ip_location():
    return 23.5204, 87.3119, "Durgapur", "West Bengal"

def get_weather_description(code):
    descriptions = {
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
        99: "Thunderstorm with heavy hail"
    }
    return descriptions.get(code, "Unknown")

def get_weather(lat, lon):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,weathercode"
            f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
            f"&current_weather=true"
            f"&timezone=auto"
        )
        data = requests.get(url).json()
        current = data.get("current_weather", {})

        utc_time_str = current.get("time", "")
        ist_time_str = "N/A"
        if utc_time_str:
            utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M")
            utc_dt = utc_dt.replace(tzinfo=pytz.utc)
            ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata"))
            ist_time_str = ist_dt.strftime("%Y-%m-%d %H:%M:%S")

        forecast_days = []
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])
        codes = daily.get("weathercode", [])
        for i in range(min(3, len(dates))):
            forecast_days.append({
                "date": dates[i],
                "temp_max": temps_max[i],
                "temp_min": temps_min[i],
                "weathercode": codes[i],
                "description": get_weather_description(codes[i])
            })

        return {
            "temperature": current.get("temperature", "N/A"),
            "windspeed": current.get("windspeed", "N/A"),
            "time": ist_time_str,
            "forecast": forecast_days
        }
    except Exception as e:
        print("Error fetching weather:", e)
        return {}

@app.route("/")
def index():
    lat, lon, city, region = get_ip_location()
    weather = get_weather(lat, lon)
    return render_template("index.html", city=city, region=region, weather=weather, now=datetime.now(pytz.timezone("Asia/Kolkata")))

@app.route("/start")
def start():
    if not hasattr(app, "ping_thread_started"):
        thread = threading.Thread(target=ping_self)
        thread.daemon = True
        thread.start()
        app.ping_thread_started = True
    return "Ping thread started."

def ping_self():
    while True:
        try:
            time.sleep(600)
            print("Pinging self...")
            requests.get("https://weather-nuo5.onrender.com/")
        except Exception as e:
            print("Ping failed:", e)

@app.route("/ping")
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(debug=True)
