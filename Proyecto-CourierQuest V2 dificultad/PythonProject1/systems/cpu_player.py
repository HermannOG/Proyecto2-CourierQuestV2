"""
CPU Player - Jugador controlado por IA
Compite contra el jugador humano en Courier Quest
"""

import random
import time
from typing import List, Optional, Tuple
from collections import deque

from models.order import Order, Position
from utils.graph import WeightedGraph, PathFinder, TSPSolver
from config.constants import MAX_WEIGHT, MAX_STAMINA


class CPUPlayer:
    """
    Clase base del jugador CPU con estado y funcionalidades comunes.
    Diseñada para ser extendida por diferentes estrategias de IA.
    """

    def __init__(self, game, difficulty: str = "easy", player_id: str = "cpu"):
        """
        Inicializa el CPU Player.

        Args:
            game: Referencia a la instancia de CourierQuest
            difficulty: Nivel de dificultad ("easy", "medium", "hard")
            player_id: Identificador único del jugador
        """
        self.game = game
        self.difficulty = difficulty
        self.player_id = player_id

        # Estado del jugador
        self.pos = Position(2, 4)  # Posición inicial diferente al humano
        self.stamina = MAX_STAMINA
        self.max_stamina = MAX_STAMINA
        self.reputation = 70
        self.money = 0
        self.max_weight = MAX_WEIGHT
        self.base_speed = 3.0

        # Gestión de pedidos
        self.inventory = deque()
        self.completed_orders = []
        self.current_target = None  # Objetivo actual (Position)
        self.current_order = None   # Orden actual (Order)
        self.current_path = []      # Camino planificado
        self.action_state = "idle"  # Estados: idle, moving_to_pickup, moving_to_dropoff

        # Estados del jugador
        self.is_exhausted = False
        self.exhaustion_recovery_threshold = 30
        self.time_since_last_move = 0
        self.last_move_time = 0
        self.move_cooldown = 0.08

        # Estadísticas
        self.delivery_streak = 0
        self.last_delivery_was_clean = True
        self.total_distance_traveled = 0

        # Estructuras de decisión (para niveles medium y hard)
        self.graph = None
        self.pathfinder = None
        self.tsp_solver = None
        self.planned_orders = []  # Secuencia de órdenes planificadas

        # Timers para decisiones
        self.decision_timer = 0
        self.decision_interval = 0.5  # Tomar decisión cada 0.5 segundos

        # Dirección visual (para rendering)
        self.direction = "east"

        print(f"✓ CPU Player inicializado - Dificultad: {difficulty.upper()}, ID: {player_id}")

    def initialize_pathfinding(self):
        """Inicializa las estructuras de grafos para pathfinding (nivel hard)."""
        if self.game.tiles and self.game.legend:
            self.graph = WeightedGraph(
                self.game.city_width,
                self.game.city_height,
                self.game.tiles,
                self.game.legend
            )
            self.pathfinder = PathFinder(self.graph)
            self.tsp_solver = TSPSolver(self.pathfinder)
            print(f"✓ Pathfinding inicializado para {self.player_id}")

    def update(self, dt: float):
        """
        Actualiza el estado del CPU Player cada frame.

        Args:
            dt: Delta time (tiempo transcurrido desde el último frame)
        """
        # Actualizar timer de decisión
        self.decision_timer += dt
        self.time_since_last_move += dt

        # Recuperación de stamina
        self._update_stamina_recovery(dt)

        # Verificar estado de exhaustión
        if self.stamina <= 0:
            self.is_exhausted = True
        elif self.stamina >= self.exhaustion_recovery_threshold:
            self.is_exhausted = False

        # Limpiar órdenes expiradas del inventario
        self._clean_expired_orders()

        # Tomar decisiones periódicamente
        if self.decision_timer >= self.decision_interval and not self.is_exhausted:
            self.make_decision(dt)
            self.decision_timer = 0

    def make_decision(self, dt: float):
        """
        Método principal de toma de decisiones.
        Debe ser sobrescrito por las estrategias específicas.
        """
        raise NotImplementedError("Subclasses must implement make_decision()")

    def execute_move(self, target_pos: Position, dt: float) -> bool:
        """
        Ejecuta un movimiento hacia una posición objetivo.

        Args:
            target_pos: Posición objetivo
            dt: Delta time

        Returns:
            True si el movimiento fue exitoso, False si no
        """
        # Verificar cooldown de movimiento
        if self.time_since_last_move < self.move_cooldown:
            return False

        # Verificar si está exhausto
        if self.is_exhausted:
            return False

        # Verificar si la posición es válida
        if not self._is_valid_move(target_pos):
            return False

        # Calcular dirección para animación
        self._update_direction(target_pos)

        # Ejecutar movimiento
        old_pos = self.pos
        self.pos = target_pos

        # Consumir stamina
        stamina_cost = self._calculate_stamina_cost(target_pos)
        self.stamina -= stamina_cost

        # Actualizar distancia viajada
        self.total_distance_traveled += 1

        # Reset del timer de movimiento
        self.last_move_time = time.time()
        self.time_since_last_move = 0

        return True

    def interact_at_position(self):
        """
        Intenta interactuar en la posición actual (pickup o delivery).
        """
        # Intentar pickup de orden
        if self.current_order and self.action_state == "moving_to_pickup":
            if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                self._pickup_order(self.current_order)
                return

        # Intentar delivery de órdenes en inventario
        for order in list(self.inventory):
            if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                self._deliver_order(order)
                return

    def _pickup_order(self, order: Order):
        """
        Recoge una orden disponible.

        Args:
            order: Orden a recoger
        """
        # Verificar capacidad
        current_weight = sum(o.weight for o in self.inventory)
        if current_weight + order.weight > self.max_weight:
            print(f"CPU {self.player_id}: Capacidad máxima alcanzada")
            self.current_order = None
            self.action_state = "idle"
            return

        # Remover de available_orders
        if order in self.game.available_orders.items:
            self.game.available_orders.items.remove(order)

        # Agregar a inventario
        order.status = "picked_up"
        order.accepted_at = self.game.game_time
        self.inventory.append(order)

        # Actualizar estado
        self.action_state = "moving_to_dropoff"
        self.current_target = order.dropoff

        print(f"CPU {self.player_id}: Orden {order.id} recogida (${order.payout})")

    def _deliver_order(self, order: Order):
        """
        Entrega una orden del inventario.

        Args:
            order: Orden a entregar
        """
        # Calcular tiempo usado
        time_used = self.game.game_time - order.accepted_at
        time_limit = order.duration_minutes * 60
        time_remaining = time_limit - time_used

        # Calcular pago y bonos
        payout = order.payout
        bonus_multiplier = 1.0

        # Bonus por entrega temprana
        if time_remaining > time_limit * 0.66:
            bonus_multiplier += 0.1
            self.reputation += 5
            self.last_delivery_was_clean = True
        elif time_remaining >= 0:
            self.reputation += 2
            self.last_delivery_was_clean = True
        else:
            # Penalización por entrega tardía
            bonus_multiplier = 0.5
            self.reputation -= 3
            self.last_delivery_was_clean = False
            self.delivery_streak = 0

        # Bonus por racha de entregas
        if self.last_delivery_was_clean:
            self.delivery_streak += 1
            if self.delivery_streak >= 3:
                streak_bonus = min(0.05 * (self.delivery_streak // 3), 0.20)
                bonus_multiplier += streak_bonus

        # Calcular pago final
        final_payout = int(payout * bonus_multiplier)
        self.money += final_payout

        # Remover del inventario
        self.inventory.remove(order)
        order.status = "delivered"
        self.completed_orders.append(order)

        # Reset estado
        self.current_order = None
        self.current_target = None
        self.action_state = "idle"

        print(f"CPU {self.player_id}: Orden {order.id} entregada - ${final_payout} (Reputación: {self.reputation})")

        # Verificar victoria
        if self.money >= self.game.goal:
            print(f"🏆 CPU {self.player_id} HA GANADO! (${self.money})")

    def _is_valid_move(self, pos: Position) -> bool:
        """
        Verifica si un movimiento es válido.

        Args:
            pos: Posición a validar

        Returns:
            True si es válido, False si no
        """
        # Verificar límites
        if not (0 <= pos.x < self.game.city_width and 0 <= pos.y < self.game.city_height):
            return False

        # Verificar que no sea un edificio
        tile_char = self.game.tiles[pos.y][pos.x]
        tile_info = self.game.legend.get(tile_char, {})
        tile_type = tile_info.get('tipo', 'street')

        return tile_type != 'building'

    def _update_direction(self, target_pos: Position):
        """
        Actualiza la dirección visual basándose en el movimiento.

        Args:
            target_pos: Posición objetivo
        """
        dx = target_pos.x - self.pos.x
        dy = target_pos.y - self.pos.y

        if abs(dx) > abs(dy):
            self.direction = "east" if dx > 0 else "west"
        else:
            self.direction = "south" if dy > 0 else "north"

    def _calculate_stamina_cost(self, pos: Position) -> float:
        """
        Calcula el costo de stamina para moverse a una posición.

        Args:
            pos: Posición objetivo

        Returns:
            Costo de stamina
        """
        base_cost = 2.0

        # Penalización por clima
        weather_penalty = self.game.weather_system.get_stamina_penalty()
        base_cost += weather_penalty

        # Penalización por peso
        current_weight = sum(o.weight for o in self.inventory)
        weight_ratio = current_weight / self.max_weight
        weight_penalty = weight_ratio * 0.5
        base_cost += weight_penalty

        return base_cost

    def _update_stamina_recovery(self, dt: float):
        """
        Actualiza la recuperación de stamina.

        Args:
            dt: Delta time
        """
        # Solo recuperar si no se ha movido recientemente
        if self.time_since_last_move < 1.0:
            return

        base_recovery = 5.0 * dt

        # Bonus en parques
        tile_char = self.game.tiles[self.pos.y][self.pos.x]
        tile_info = self.game.legend.get(tile_char, {})
        tile_type = tile_info.get('tipo', 'street')

        if tile_type == 'park':
            base_recovery += 15.0 * dt

        self.stamina = min(self.stamina + base_recovery, self.max_stamina)

    def _clean_expired_orders(self):
        """Limpia órdenes expiradas del inventario."""
        expired = []
        for order in list(self.inventory):
            time_limit = order.duration_minutes * 60
            if self.game.game_time - order.accepted_at > time_limit * 1.5:
                expired.append(order)

        for order in expired:
            self.inventory.remove(order)
            self.reputation -= 6
            self.delivery_streak = 0
            print(f"CPU {self.player_id}: Orden {order.id} expirada (-6 reputación)")

        # Verificar game over por reputación
        if self.reputation < 20:
            print(f"💀 CPU {self.player_id} perdió por baja reputación")

    def get_available_orders(self) -> List[Order]:
        """
        Obtiene las órdenes disponibles para el CPU.

        Returns:
            Lista de órdenes disponibles
        """
        # Retornar órdenes de la cola compartida
        return [order for order in self.game.available_orders.items if order.status == "available"]

    def get_current_weight(self) -> int:
        """Retorna el peso actual del inventario."""
        return sum(o.weight for o in self.inventory)

    def has_capacity_for(self, order: Order) -> bool:
        """
        Verifica si hay capacidad para una orden.

        Args:
            order: Orden a verificar

        Returns:
            True si hay capacidad, False si no
        """
        return self.get_current_weight() + order.weight <= self.max_weight

    def get_weather_penalty(self) -> float:
        """Obtiene la penalización actual del clima."""
        return self.game.weather_system.get_stamina_penalty()

    def is_low_stamina(self) -> bool:
        """Verifica si el stamina está bajo."""
        return self.stamina < 30

    def find_nearest_park(self) -> Optional[Position]:
        """
        Encuentra el parque más cercano para recuperar stamina.

        Returns:
            Posición del parque más cercano, o None si no hay
        """
        nearest_park = None
        min_distance = float('inf')

        for y in range(self.game.city_height):
            for x in range(self.game.city_width):
                tile_char = self.game.tiles[y][x]
                tile_info = self.game.legend.get(tile_char, {})

                if tile_info.get('tipo') == 'park':
                    park_pos = Position(x, y)
                    distance = abs(park_pos.x - self.pos.x) + abs(park_pos.y - self.pos.y)

                    if distance < min_distance:
                        min_distance = distance
                        nearest_park = park_pos

        return nearest_park

    def __repr__(self):
        """Representación en string del CPU Player."""
        return (f"CPUPlayer(id={self.player_id}, difficulty={self.difficulty}, "
                f"pos=({self.pos.x},{self.pos.y}), money=${self.money}, "
                f"reputation={self.reputation}, stamina={self.stamina:.1f})")
