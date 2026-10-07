import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone

import database as db
import events
from prediction import predict_wait
from schemas import (EmployeesIn, LocationIn, OrderCreate, OrderOut, OrderStatusOut,
                     PredictIn, PredictOut, QueueOut)
from weather import get_weather

db.init_db()
model = joblib.load("waiting_time_model.joblib")
app = FastAPI(title="TimePred API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173" , "http://127.0.0.1:5173"],     
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_restaurant(restaurant_id: int) -> dict:
    restaurant = db.get_restaurant(restaurant_id)
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    return restaurant


def change_state(order_id: int, action) -> dict:
    if db.get_order(order_id) is None:
        raise HTTPException(404, "Order not found")
    if action(order_id) == 0:
        raise HTTPException(409, "That order is not in a state where this action is allowed")
    events.notify()
    return db.get_order(order_id)


@app.get("/")
def home():
    return {"message": "TimePred API is running"}


@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate | None = None):
    body = body or OrderCreate()
    require_restaurant(body.restaurant_id)
    order = db.create_order(body.restaurant_id, body.item_count)
    events.notify()
    return order


@app.put("/orders/{order_id}/start", response_model=OrderOut)
def start_order(order_id: int):
    return change_state(order_id, db.start_order)


@app.put("/orders/{order_id}/complete", response_model=OrderOut)
def complete_order(order_id: int):
    return change_state(order_id, db.complete_order)


@app.get("/orders/{order_id}/status", response_model=OrderStatusOut)
def order_status(order_id: int):
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    restaurant = require_restaurant(order["restaurant_id"])

    if order["status"] == "COMPLETED":
        return {"id": order_id, "status": "COMPLETED", "orders_ahead": 0, "eta_minutes": 0}

    if order["status"] == "IN_PROGRESS":
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(order["started_at"])).total_seconds() / 60
        eta = max(1.0, db.avg_service_minutes(restaurant["id"]) - elapsed)
        return {"id": order_id, "status": "IN_PROGRESS", "orders_ahead": 0, "eta_minutes": round(eta, 1)}

    ahead_waiting = db.waiting_ahead_of(order)
    eta = predict_wait(model, restaurant, waiting=ahead_waiting)["predicted_waiting_time"]
    return {"id": order_id, "status": "CREATED", "orders_ahead": ahead_waiting , "eta_minutes": eta}


@app.get("/queue", response_model=QueueOut)
def get_queue(restaurant_id: int = 1):
    restaurant = require_restaurant(restaurant_id)
    return {
        "orders": db.list_queue_orders(restaurant_id, restaurant["timezone"]),
        "employees_working": restaurant["employees_working"],
    }


@app.put("/employees")
def update_employees(body: EmployeesIn):
    require_restaurant(body.restaurant_id)
    db.set_employees(body.restaurant_id, body.employees_working)
    events.notify()
    return {"message": "Employee count updated", "employees_working": body.employees_working}


@app.put("/restaurant/location")
def update_location(body: LocationIn):
    require_restaurant(body.restaurant_id)
    try:
        timezone_name = get_weather(body.latitude, body.longitude)["timezone"]
    except Exception:
        raise HTTPException(502, "Could not look up the timezone for these coordinates. Try again.")
    db.set_location(body.restaurant_id, body.latitude, body.longitude, timezone_name)
    events.notify()
    return {"latitude": body.latitude, "longitude": body.longitude, "timezone": timezone_name}


@app.post("/predict", response_model=PredictOut)
def predict(body: PredictIn | None = None):
    body = body or PredictIn()
    restaurant = require_restaurant(body.restaurant_id)
    return predict_wait(model, restaurant, lat=body.latitude, lon=body.longitude)


@app.get("/analytics/hourly")
def analytics_hourly(restaurant_id: int = 1):
    restaurant = require_restaurant(restaurant_id)
    return db.hourly_analytics(restaurant_id, restaurant["timezone"])


@app.get("/events")
async def events_stream(request: Request):
    return StreamingResponse(
        events.event_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )