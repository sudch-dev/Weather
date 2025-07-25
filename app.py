from flask import Flask, render_template
import requests
from datetime import datetime

app = Flask(__name__)

def get_ip_location():
    try:
        ip = requests.get("https://api.ipify.org").text
        location = requests.get(f"https://ipinfo.io/{ip}/json").json()
        loc = location.get("loc", "")
        city = location.get("city", "Unknown")
        region = location.get("region", "Unknown")
        lat, lon = loc.split(",") if loc else ("0", "0")
        return float(lat), float(lon), city, region
    except:
        return None, None, "Unknown", "Unknown"

def get_weather(lat, lon):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,relative_humidity_2m,weathercode"
            f"&current_weather=true"
        )
        data = requests.get(url).json()
        current = data.get("current_weather", {})
        return {
            "temperature": current.get("temperature", "N/A"),
            "windspeed": current.get("windspeed", "N/A"),
            "time": current.get("time", "")
        }
    except:
        return {}

@app.route("/")
def index():
    lat, lon, city, region = get_ip_location()
    weather = get_weather(lat, lon)
    return render_template("index.html", city=city, region=region, weather=weather, now=datetime.now())

if __name__ == "__main__":
    app.run(debug=True)
