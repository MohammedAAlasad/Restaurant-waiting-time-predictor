import httpx


def get_weather():

    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "current": "temperature_2m,weather_code,wind_speed_10m"
    }

    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params=params
    )

    data = response.json()

    temperature = data["current"]["temperature_2m"]
    weather_code = data["current"]["weather_code"]
    wind_speed = data["current"]["wind_speed_10m"]

    weather = convert_weather(weather_code, wind_speed)

    return temperature, weather


def convert_weather(code, wind_speed):

    if code in [95, 96, 99]:
        return "Stormy"

    elif code in [
        51, 53, 55, 56, 57,
        61, 63, 65, 66, 67,
        80, 81, 82
    ]:
        return "Rainy"

    elif code in [1, 2, 3, 45, 48]:
        return "Cloudy"

    elif wind_speed >= 30:
        return "Windy"

    else:
        return "Sunny"