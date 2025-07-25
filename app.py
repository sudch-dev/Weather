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

        # Convert UTC time to IST for current weather
        utc_time_str = current.get("time", "")
        ist_time_str = "N/A"
        if utc_time_str:
            utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M")
            utc_dt = utc_dt.replace(tzinfo=pytz.utc)
            ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata"))
            ist_time_str = ist_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Forecast data (next 3 days max/min temperatures)
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
                "weathercode": codes[i]
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

@app.route("/ping")
def ping():
    return "pong"

# Background ping every 10 mins
def ping_self():
    while True:
        try:
            time.sleep(600)  # 10 minutes
            print("Pinging self...")
            requests.get("http://127.0.0.1:5000/ping")  # Replace with full URL if hosted
        except Exception as e:
            print("Ping failed:", e)

@app.before_first_request
def activate_ping_thread():
    thread = threading.Thread(target=ping_self)
    thread.daemon = True
    thread.start()

if __name__ == "__main__":
    app.run(debug=True)
