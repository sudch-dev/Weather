import requests
import time
from datetime import datetime

def get_ip_location():
    try:
        ip = requests.get("https://api.ipify.org").text
        location = requests.get(f"https://ipinfo.io/{ip}/json").json()
        loc = location.get("loc", "")
        city = location.get("city", "Unknown")
        region = location.get("region", "Unknown")
        lat, lon = loc.split(",") if loc else ("0", "0")
        return float(lat), float(lon), city, region
    except Exception as e:
        print("Error fetching location:", e)
        return None, None, "Unknown", "Unknown"

def get_weather(lat, lon):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,relative_humidity_2m,weathercode"
            f"&current_weather=true"
        )
        response = requests.get(url)
        data = response.json()
        current = data.get("current_weather", {})
        temp = current.get("temperature", "N/A")
        wind = current.get("windspeed", "N/A")
        time_stamp = current.get("time", "")
        print(f"\n📍 Weather Update @ {time_stamp}")
        print(f"Temperature: {temp}°C")
        print(f"Wind Speed: {wind} km/h")
    except Exception as e:
        print("Error fetching weather:", e)

def main():
    print("🔄 Weather Reporter Started! Will update every 2 hours...\n")
    lat, lon, city, region = get_ip_location()
    if lat is None:
        return
    print(f"📍 Location detected: {city}, {region} ({lat}, {lon})")

    while True:
        print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        get_weather(lat, lon)
        time.sleep(7200)  # 2 hours = 7200 seconds

if __name__ == "__main__":
    main()
