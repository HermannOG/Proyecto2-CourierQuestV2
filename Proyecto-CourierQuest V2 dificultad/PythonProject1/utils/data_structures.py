# utils/data_structures.py
from typing import Optional
from models.order import Order
from models.game_state import GameState, Position


class OptimizedPriorityQueue:
    def __init__(self):
        self.items = []

    def enqueue(self, item: Order):
        if not self.items:
            self.items.append(item)
            return

        left, right = 0, len(self.items)
        while left < right:
            mid = (left + right) // 2
            if self.items[mid].priority < item.priority:
                right = mid
            else:
                left = mid + 1

        self.items.insert(left, item)

    def dequeue(self) -> Optional[Order]:
        return self.items.pop(0) if self.items else None

    def size(self) -> int:
        return len(self.items)

    def remove(self, order: Order) -> bool:
        try:
            self.items.remove(order)
            return True
        except ValueError:
            return False


class MemoryEfficientHistory:
    def __init__(self, max_size: int = 20):
        self.diffs = []
        self.max_size = max_size
        self.base_state = None

    def push(self, state: GameState):
        if self.base_state is None:
            self.base_state = state
            return

        diff = {}
        if (self.base_state.player_pos.x != state.player_pos.x or
                self.base_state.player_pos.y != state.player_pos.y):
            diff['player_pos'] = (state.player_pos.x, state.player_pos.y)

        if abs(self.base_state.stamina - state.stamina) > 1.0:
            diff['stamina'] = state.stamina

        if self.base_state.money != state.money:
            diff['money'] = state.money

        if self.base_state.reputation != state.reputation:
            diff['reputation'] = state.reputation

        if diff:
            self.diffs.append(diff)
            if len(self.diffs) >= self.max_size:
                self.diffs.pop(0)

    def pop(self) -> Optional[GameState]:
        if not self.diffs:
            return None

        diff = self.diffs.pop()
        new_state = GameState(
            player_pos=Position(
                diff.get('player_pos', (self.base_state.player_pos.x, self.base_state.player_pos.y))[0],
                diff.get('player_pos', (self.base_state.player_pos.x, self.base_state.player_pos.y))[1]
            ),
            stamina=diff.get('stamina', self.base_state.stamina),
            reputation=diff.get('reputation', self.base_state.reputation),
            money=diff.get('money', self.base_state.money),
            game_time=self.base_state.game_time,
            weather_time=self.base_state.weather_time,
            current_weather=self.base_state.current_weather,
            weather_intensity=self.base_state.weather_intensity,
            inventory=list(self.base_state.inventory),
            available_orders=list(self.base_state.available_orders),
            completed_orders=list(self.base_state.completed_orders),
            goal=self.base_state.goal,
            delivery_streak=0,
            pending_orders=list(getattr(self.base_state, 'pending_orders', [])),
            city_width=getattr(self.base_state, 'city_width', 30),
            city_height=getattr(self.base_state, 'city_height', 25),
            tiles=getattr(self.base_state, 'tiles', []),
            legend=getattr(self.base_state, 'legend', {}),
            city_name=getattr(self.base_state, 'city_name', 'TigerCity'),
            max_game_time=getattr(self.base_state, 'max_game_time', 600.0)
        )
        return new_state

    def size(self) -> int:
        return len(self.diffs)