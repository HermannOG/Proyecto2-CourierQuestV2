# systems/sorting.py
from typing import List
from models.order import Order, Position


class SortingAlgorithms:
    @staticmethod
    def quicksort_by_priority(orders: List[Order]) -> List[Order]:
        if len(orders) <= 1:
            return orders.copy()

        pivot = orders[len(orders) // 2]
        left = [x for x in orders if x.priority > pivot.priority]
        middle = [x for x in orders if x.priority == pivot.priority]
        right = [x for x in orders if x.priority < pivot.priority]

        return (SortingAlgorithms.quicksort_by_priority(left) +
                middle +
                SortingAlgorithms.quicksort_by_priority(right))

    @staticmethod
    def mergesort_by_deadline(orders: List[Order], game_time: float) -> List[Order]:
        if len(orders) <= 1:
            return orders.copy()

        mid = len(orders) // 2
        left = SortingAlgorithms.mergesort_by_deadline(orders[:mid], game_time)
        right = SortingAlgorithms.mergesort_by_deadline(orders[mid:], game_time)

        return SortingAlgorithms._merge_by_deadline(left, right, game_time)

    @staticmethod
    def _merge_by_deadline(left: List[Order], right: List[Order], game_time: float) -> List[Order]:
        result = []
        i = j = 0

        def get_time_remaining(order):
            if order.status == "waiting_release":
                return order.duration_minutes * 60
            elapsed = game_time - order.created_at
            return max(0, order.duration_minutes * 60 - elapsed)

        while i < len(left) and j < len(right):
            if get_time_remaining(left[i]) <= get_time_remaining(right[j]):
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1

        result.extend(left[i:])
        result.extend(right[j:])
        return result

    @staticmethod
    def insertion_sort_by_distance(orders: List[Order], player_pos: Position) -> List[Order]:
        result = orders.copy()

        def manhattan_distance(order):
            return abs(order.pickup.x - player_pos.x) + abs(order.pickup.y - player_pos.y)

        for i in range(1, len(result)):
            key = result[i]
            key_distance = manhattan_distance(key)
            j = i - 1

            while j >= 0 and manhattan_distance(result[j]) > key_distance:
                result[j + 1] = result[j]
                j -= 1

            result[j + 1] = key

        return result