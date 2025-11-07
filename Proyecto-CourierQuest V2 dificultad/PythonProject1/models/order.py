# models/order.py
from dataclasses import dataclass


@dataclass
class Position:
    x: int
    y: int


@dataclass
class Order:
    id: str
    pickup: Position
    dropoff: Position
    payout: int
    duration_minutes: float
    weight: int
    priority: int
    release_time: int
    status: str = "waiting_release"
    created_at: float = 0.0
    accepted_at: float = 0.0