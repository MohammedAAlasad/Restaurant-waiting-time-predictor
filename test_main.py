import os

os.environ["DB_PATH"] = "test_restaurant.db"

# Start every run with a clean database (must happen BEFORE importing main)
if os.path.exists("test_restaurant.db"):
    os.remove("test_restaurant.db")

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_home():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "TimePred API is running"
    }


def test_create_order():
    response = client.post("/orders")

    assert response.status_code == 201

    order = response.json()
    assert order["id"] >= 1
    assert order["status"] == "CREATED"


def test_update_employees():
    response = client.put(
        "/employees",
        json={"employees_working": 5}
    )

    assert response.status_code == 200
    assert response.json()["employees_working"] == 5


def test_start_order():
    # Create an order first
    order_id = client.post("/orders").json()["id"]

    response = client.put(f"/orders/{order_id}/start")

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_complete_order():
    # Create
    order_id = client.post("/orders").json()["id"]

    # Start
    client.put(f"/orders/{order_id}/start")

    # Complete
    response = client.put(f"/orders/{order_id}/complete")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


def test_start_nonexistent_order():
    response = client.put("/orders/999999/start")

    assert response.status_code == 404


def test_complete_nonexistent_order():
    response = client.put("/orders/999999/complete")

    assert response.status_code == 404


def test_start_order_twice_is_conflict():
    order_id = client.post("/orders").json()["id"]
    client.put(f"/orders/{order_id}/start")

    response = client.put(f"/orders/{order_id}/start")

    assert response.status_code == 409


def test_queue():
    order_id = client.post("/orders").json()["id"]

    response = client.get("/queue")

    assert response.status_code == 200
    data = response.json()
    assert order_id in [o["id"] for o in data["orders"]]
    assert data["employees_working"] >= 1


def test_predict():
    response = client.post("/predict")

    assert response.status_code == 200

    data = response.json()

    assert "predicted_waiting_time" in data
    assert "warnings" in data

    assert isinstance(data["predicted_waiting_time"], (int, float))
    assert data["predicted_waiting_time"] >= 0
    assert isinstance(data["warnings"], list)