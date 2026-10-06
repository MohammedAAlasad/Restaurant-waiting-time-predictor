import time
import httpx

_CACHE: dict = {}
CACHE_SECONDS = 600  

def get_weather(latitude: float, longitude: float) -> dict:
    key = (round(latitude, 2), round(longitude, 2))
    hit = _CACHE.get(key)
    if hit and time.time() - hit["at"] < CACHE_SECONDS:
        return hit["data"]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "timezone": "auto",   
    }

    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast", params=params, timeout=5.0
        )
        response.raise_for_status()
        body = response.json()
        current = body["current"]
        data = {
            "temperature": current["temperature_2m"],
            "weather": convert_weather(current["weather_code"], current["wind_speed_10m"]),
            "timezone": body["timezone"],
        }
    except (httpx.HTTPError, KeyError, ValueError):
        if hit:          
            return hit["data"]
        raise

    _CACHE[key] = {"at": time.time(), "data": data}
    return data


def convert_weather(code, wind_speed):
    # unchanged from your original, so labels still match your training data
    if code in [95, 96, 99]:
        return "Stormy"
    elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
        return "Rainy"
    elif code in [1, 2, 3, 45, 48]:
        return "Cloudy"
    elif wind_speed >= 30:
        return "Windy"
    else:
        return "Sunny"