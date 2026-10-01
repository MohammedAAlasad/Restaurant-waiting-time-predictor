import os

# IMPORTANT: Must be set BEFORE importing main/database
os.environ["DB_PATH"] = "test_restaurant.db"

from fastapi.testclient import TestClient

from main import app
from database import get_orders_count


client = TestClient(app)


def test_home():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "TimePred API is running"
    }


def test_create_order():
    before = get_orders_count()

    response = client.post("/orders")

    after = get_orders_count()

    assert response.status_code == 200

    assert response.json() == {
        "message": "Order created successfully"
    }

    assert after == before + 1

def test_update_employees():
    response = client.put(
        "/employees",
        json={"employees_working": 5}
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Employee count edited successfully"
    }


def test_start_order():
    # Create an order first
    client.post("/orders")

    order_id = get_orders_count()

    response = client.put(f"/orders/{order_id}/start")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Order started successfully"
    }


def test_complete_order():
    # Create
    client.post("/orders")
    order_id = get_orders_count()

    # Start
    client.put(f"/orders/{order_id}/start")

    # Complete
    response = client.put(f"/orders/{order_id}/complete")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Order ended successfully"
    }


def test_start_nonexistent_order():
    response = client.put("/orders/999999/start")

    assert response.status_code == 404


def test_complete_nonexistent_order():
    response = client.put("/orders/999999/complete")

    assert response.status_code == 404

def test_predict():
    response = client.post("/predict")

    assert response.status_code == 200

    data = response.json()

    assert "predicted_waiting_time" in data
    assert "warnings" in data

    assert isinstance(data["predicted_waiting_time"], (int, float))
    assert data["predicted_waiting_time"] >= 0
    assert isinstance(data["warnings"], list)