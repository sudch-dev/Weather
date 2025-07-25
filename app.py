from flask import Flask, render_template
import requests
from datetime import datetime
import pytz

app = Flask(__name__)

# Fixed Durgapur, West Bengal location
def get_ip_location():
    return 23.5204, 87.3119, "Durgapur", "West Bengal"

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
        
        # Convert UTC time to IST
        utc_time_str = current.get("time", "")
        ist_time_str = "N/A"
        if utc_time_str:
            utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M")
            utc_dt = utc_dt.replace(tzinfo=pytz.utc)
            ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata"))
            ist_time_str = ist_dt.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "temperature": current.get("temperature", "N/A"),
            "windspeed": current.get("windspeed", "N/A"),
            "time": ist_time_str
        }
    except:
        return {}

@app.route("/")
def index():
    lat, lon, city, region = get_ip_location()
    weather = get_weather(lat, lon)
    return render_template("index.html", city=city, region=region, weather=weather, now=datetime.now(pytz.timezone("Asia/Kolkata")))

if __name__ == "__main__":
    app.run(debug=True)
