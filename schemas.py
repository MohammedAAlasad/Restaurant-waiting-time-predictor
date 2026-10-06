from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["CREATED", "IN_PROGRESS", "COMPLETED"]


class OrderCreate(BaseModel):
    restaurant_id: int = 1
    item_count: int = Field(default=1, ge=1)


class OrderOut(BaseModel):
    id: int
    restaurant_id: int
    status: Status
    item_count: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class QueueOut(BaseModel):
    orders: list[OrderOut]
    employees_working: int


class OrderStatusOut(BaseModel):
    id: int
    status: Status
    orders_ahead: int
    eta_minutes: float


class EmployeesIn(BaseModel):
    employees_working: int = Field(ge=1)
    restaurant_id: int = 1


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    restaurant_id: int = 1


class PredictIn(BaseModel):
    restaurant_id: int = 1
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class PredictOut(BaseModel):
    predicted_waiting_time: float
    warnings: list[str]