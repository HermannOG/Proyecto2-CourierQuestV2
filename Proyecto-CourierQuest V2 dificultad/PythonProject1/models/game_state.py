# models/game_state.py
from dataclasses import dataclass
from typing import List, Dict
from models.order import Position, Order


@dataclass
class GameState:
    player_pos: Position
    stamina: float
    reputation: int
    money: int
    game_time: float
    weather_time: float
    current_weather: str
    weather_intensity: float
    inventory: List[Order]
    available_orders: List[Order]
    completed_orders: List[Order]
    goal: int
    delivery_streak: int
    pending_orders: List[Order]
    city_width: int
    city_height: int
    tiles: List[List[str]]
    legend: Dict
    city_name: str
    max_game_time: float