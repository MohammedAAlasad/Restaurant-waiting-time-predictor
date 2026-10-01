from fastapi import FastAPI , HTTPException
from pydantic import BaseModel , Field

import pandas as pd
import joblib

import holidays
from weather import get_weather

from zoneinfo import ZoneInfo
from datetime import datetime

from database import get_customers_in_queue, get_employees_working,get_avg_service_time, get_orders_last_30min
from database import create_order , start_order , end_order , update_employees_working

app = FastAPI()
model = joblib.load('waiting_time_model.joblib')

class EmployeesUpdate(BaseModel):
    employees_working: int = Field(ge=1)

@app.get("/")
def home():
    return {"message" : "TimePred API is running"}

@app.post("/predict")
def predict():
    customers_in_queue = get_customers_in_queue()
    employees_working = get_employees_working()
    avg_service_time = get_avg_service_time()
    orders_last_30min = get_orders_last_30min()

    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    temperature, weather = get_weather()

    warnings = []

    us_holidays = holidays.US(years=now.year)
    is_holiday = 1 if now.date() in us_holidays else 0

    hour = now.hour
    day_of_week = now.strftime("%A")
    is_weekend = 1 if day_of_week in ["Saturday", "Sunday"] else 0
    
    new_data = pd.DataFrame(
    [{
        "day_of_week": day_of_week,
        "hour": hour,
        "is_weekend": is_weekend,
        "is_holiday": is_holiday,
        "temperature": temperature,
        "weather": weather,
        "customers_in_queue": customers_in_queue,
        "employees_working": employees_working,
        "avg_service_time": avg_service_time,
        "orders_last_30min": orders_last_30min
    }]
    )

    if customers_in_queue > 31:
        warnings.append(
            "customers_in_queue is outside the training range"
        )

    if employees_working > 9:
        warnings.append(
            "employees_working is outside the training range"
        )

    if avg_service_time < 2.09 or avg_service_time > 10.68:
        warnings.append(
            "avg_service_time is outside the training range"
        )

    if orders_last_30min > 61:
        warnings.append(
            "orders_last_30min is outside the training range"
        )


    pred = model.predict(new_data)
    return {
        "predicted_waiting_time":max(0, float(pred[0])),
        "warnings": warnings
        }
    

@app.post("/orders")
def create_order_endpoint():
    create_order()

    return {
        "message": "Order created successfully"
    } 

@app.put("/orders/{order_id}/start")
def start_order_endpoint(order_id: int):
    row_chnage_result = start_order(order_id)
    if row_chnage_result == 1:
        return {
            "message": "Order started successfully"
        } 
    else:
        raise HTTPException(
        status_code=404,
        detail="Order not found"
    )

@app.put("/orders/{order_id}/complete")
def complete_order_endpoint(order_id: int):
    row_chnage_result = end_order(order_id)
    if row_chnage_result == 1:
        return {
            "message": "Order ended successfully"
        } 
    else:
        raise HTTPException(
        status_code=404,
        detail="Order not found"
    )

    
@app.put("/employees")
def update_employees(data: EmployeesUpdate):
    up_emp = update_employees_working(data.employees_working)
    if up_emp == 0:
        raise HTTPException(
            status_code=404,
            detail="Restaurant info not found"
        )

    return {
        "message": "Employee count edited successfully"
    }

        