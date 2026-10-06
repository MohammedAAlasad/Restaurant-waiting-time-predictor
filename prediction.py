from datetime import datetime
from zoneinfo import ZoneInfo

import holidays
import pandas as pd

import database as db
from weather import get_weather

DEFAULT_TEMPERATURE = 20.0
DEFAULT_WEATHER = "Sunny"

def predict_wait(model, restaurant: dict, lat=None, lon=None, waiting: int | None = None) -> dict:
   
    rid = restaurant["id"]
    warnings: list[str] = []
    now = datetime.now(ZoneInfo(restaurant["timezone"]))

    lat = lat if lat is not None else restaurant["latitude"]
    lon = lon if lon is not None else restaurant["longitude"]

    temperature, weather = DEFAULT_TEMPERATURE, DEFAULT_WEATHER
    if lat is not None and lon is not None:
        try:
            wx = get_weather(lat, lon)
            temperature, weather = wx["temperature"], wx["weather"]
        except Exception:
            warnings.append("weather unavailable; using typical values")
    else:
        warnings.append("no location set; using typical weather")

    queue_waiting, _ = db.queue_counts(rid)
    customers_in_queue = queue_waiting if waiting is None else waiting
    employees = restaurant["employees_working"]
    avg_service = db.avg_service_minutes(rid)
    last_30 = db.orders_created_last_minutes(rid, 30)

    day_name = now.strftime("%A")
    country_holidays = holidays.country_holidays(restaurant["country_code"], years=now.year)

    row = pd.DataFrame([{
        "day_of_week": day_name,
        "hour": str(now.hour),
        "is_weekend": int(day_name in ("Saturday", "Sunday")),
        "is_holiday": int(now.date() in country_holidays),
        "temperature": temperature,
        "weather": weather,
        "customers_in_queue": customers_in_queue,
        "employees_working": employees,
        "avg_service_time": avg_service,
        "orders_last_30min": last_30,
    }])

    if customers_in_queue > 31:
        warnings.append("customers_in_queue is outside the training range")
    if employees > 9:
        warnings.append("employees_working is outside the training range")
    if not 2.09 <= avg_service <= 10.68:
        warnings.append("avg_service_time is outside the training range")
    if last_30 > 61:
        warnings.append("orders_last_30min is outside the training range")

    prediction = float(model.predict(row)[0])
    return {"predicted_waiting_time": round(max(0.0, prediction), 1), "warnings": warnings}