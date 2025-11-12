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

        # Estado del jugador - POSICIÓN INICIAL SERÁ ASIGNADA DESPUÉS
        self.pos = None
        self.stamina = MAX_STAMINA
        self.max_stamina = MAX_STAMINA
        self.reputation = 70
        self.money = 0
        self.max_weight = MAX_WEIGHT
        self.base_speed = 3.0

        # Gestión de pedidos
        self.inventory = deque()
        self.completed_orders = []
        self.current_target = None
        self.current_order = None
        self.current_path = []
        self.action_state = "idle"

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

        # Estructuras de decisión
        self.graph = None
        self.pathfinder = None
        self.tsp_solver = None
        self.planned_orders = []

        # Timers para decisiones
        self.decision_timer = 0
        self.decision_interval = 0.1

        # Dirección visual
        self.direction = "east"

        # Asignar posición inicial válida
        self._find_valid_starting_position()

        print(
            f"✓ CPU Player inicializado - Dificultad: {difficulty.upper()}, ID: {player_id}, Pos: ({self.pos.x},{self.pos.y})")

    def _find_valid_starting_position(self):
        """Encuentra una posición inicial válida para el CPU (que no sea edificio)."""
        candidate_positions = [
            (5, 5), (6, 6), (7, 7), (4, 4), (3, 5),
            (5, 3), (6, 4), (4, 6), (7, 5), (5, 7),
            (8, 8), (9, 9), (3, 7), (7, 3)
        ]

        for x, y in candidate_positions:
            if self._is_position_valid_for_cpu(x, y):
                self.pos = Position(x, y)
                return

        for y in range(self.game.city_height):
            for x in range(self.game.city_width):
                distance_to_player = abs(x - self.game.player_pos.x) + abs(y - self.game.player_pos.y)
                if distance_to_player >= 3 and self._is_position_valid_for_cpu(x, y):
                    self.pos = Position(x, y)
                    return

        for y in range(self.game.city_height):
            for x in range(self.game.city_width):
                if self._is_position_valid_for_cpu(x, y):
                    self.pos = Position(x, y)
                    return

        self.pos = Position(5, 5)
        print(f" CPU usando posición fallback: (5, 5)")

    def _is_position_valid_for_cpu(self, x: int, y: int) -> bool:
        """Verifica si una posición es válida para iniciar el CPU."""
        if not (0 <= x < self.game.city_width and 0 <= y < self.game.city_height):
            return False

        if y >= len(self.game.tiles) or x >= len(self.game.tiles[y]):
            return False

        tile_char = self.game.tiles[y][x]
        tile_info = self.game.legend.get(tile_char, {})
        tile_type = tile_info.get('tipo', 'street')
        is_blocked = tile_info.get('blocked', False)

        return tile_type != 'building' and not is_blocked

    def initialize_pathfinding(self):
        """
        Inicializa las estructuras de grafos para pathfinding.
        MEJORADO: Más validaciones y logging.
        """
        try:
            if not self.game.tiles or not self.game.legend:
                print(f" CPU {self.player_id}: No hay tiles o legend disponibles")
                self.graph = None
                self.pathfinder = None
                self.tsp_solver = None
                return

            print(f"CPU {self.player_id}: Construyendo grafo de pathfinding...")

            self.graph = WeightedGraph(
                self.game.city_width,
                self.game.city_height,
                self.game.tiles,
                self.game.legend
            )

            self.pathfinder = PathFinder(self.graph)
            self.tsp_solver = TSPSolver(self.pathfinder)

            # Debug: Verificar el grafo
            self.debug_pathfinding_graph()

            print(f"✓ CPU {self.player_id}: Pathfinding inicializado correctamente")

        except Exception as e:
            print(f"✗ CPU {self.player_id}: Error inicializando pathfinding: {e}")
            import traceback
            traceback.print_exc()
            self.graph = None
            self.pathfinder = None
            self.tsp_solver = None

    def update(self, dt: float):
        """
        Actualiza el estado del CPU Player cada frame.
        MEJORADO: Mejor manejo de exhausto y recuperación.
        """
        self.decision_timer += dt
        self.time_since_last_move += dt

        # SIEMPRE actualizar recuperación de stamina
        self._update_stamina_recovery(dt)

        # Verificar si se recuperó del exhausto
        if self.stamina <= 0:
            self.is_exhausted = True
        elif self.stamina >= self.exhaustion_recovery_threshold:
            if self.is_exhausted:
                print(f"CPU {self.player_id}: ✅ Recuperado ({self.stamina:.1f}/{self.exhaustion_recovery_threshold})")
            self.is_exhausted = False

        self._clean_expired_orders()

        # Solo tomar decisiones si NO está exhausto
        if self.decision_timer >= self.decision_interval and not self.is_exhausted:
            self.make_decision(dt)
            self.decision_timer = 0
        elif self.is_exhausted:
            # Si está exhausto, mostrar mensaje periódicamente
            if not hasattr(self, '_last_exhausted_message'):
                self._last_exhausted_message = 0

            current_time = time.time()
            if current_time - self._last_exhausted_message > 3.0:
                remaining = self.exhaustion_recovery_threshold - self.stamina
                print(f"CPU {self.player_id}: ⏸️ EXHAUSTO - Esperando recuperar {remaining:.1f} pts más")
                self._last_exhausted_message = current_time

    def make_decision(self, dt: float):
        """Método principal de toma de decisiones."""
        raise NotImplementedError("Subclasses must implement make_decision()")

    def execute_move(self, target_pos: Position, dt: float) -> bool:
        """
        Ejecuta un movimiento hacia una posición objetivo.
        MEJORADO: Se detiene completamente si no hay suficiente stamina.
        """
        if self.time_since_last_move < self.move_cooldown:
            return False

        # CRÍTICO: No moverse si está exhausto
        if self.is_exhausted:
            return False

        if not self._is_valid_move(target_pos):
            return False

        # NUEVO: Calcular el costo ANTES de moverse y verificar si hay suficiente stamina
        stamina_cost = self._calculate_stamina_cost(target_pos)

        # Si no hay suficiente stamina para el movimiento, NO moverse
        if self.stamina < stamina_cost:
            print(f"CPU {self.player_id}: Stamina insuficiente para moverse ({self.stamina:.1f} < {stamina_cost:.1f})")
            return False

        self._update_direction(target_pos)

        old_pos = self.pos
        self.pos = target_pos

        # Restar stamina DESPUÉS de validar que hay suficiente
        self.stamina -= stamina_cost

        self.total_distance_traveled += 1

        self.last_move_time = time.time()
        self.time_since_last_move = 0

        # Verificar si quedó exhausto después del movimiento
        if self.stamina <= 0:
            self.is_exhausted = True
            print(f"CPU {self.player_id}: ¡EXHAUSTO! ({self.stamina:.1f}/{self.exhaustion_recovery_threshold})")

        return True

    def interact_at_position(self):
        """
        Intenta interactuar en la posición actual (pickup o delivery).
        CORREGIDO: Maneja correctamente el estado de las órdenes.
        """
        # Caso 1: Entregar pedido si está en dropoff
        if self.inventory:
            for order in list(self.inventory):
                if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                    self._deliver_order(order)
                    return True

        # Caso 2: Recoger pedido si está en pickup
        if self.current_order:
            # Verificar que la orden sigue disponible
            if self.current_order not in self.game.available_orders.items:
                print(f"CPU {self.player_id}: Orden {self.current_order.id} ya no está disponible")
                self.current_order = None
                self.action_state = "idle"
                return False

            # Verificar que está en la posición correcta
            if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                current_weight = self.get_current_weight()
                if current_weight + self.current_order.weight <= self.max_weight:
                    # Recoger el pedido
                    self.current_order.status = "in_progress"
                    self.current_order.accepted_at = self.game.game_time
                    self.inventory.append(self.current_order)

                    # Remover de disponibles
                    if self.current_order in self.game.available_orders.items:
                        self.game.available_orders.items.remove(self.current_order)

                    print(f"CPU {self.player_id}: Recogió orden {self.current_order.id}")

                    # Cambiar estado a delivery
                    self.action_state = "moving_to_dropoff"
                    self.current_target = self.current_order.dropoff

                    # Limpiar el camino para recalcular
                    self.current_path = []
                    self.path_index = 0

                    return True
                else:
                    print(f"CPU {self.player_id}: No hay capacidad para orden {self.current_order.id}")
                    self.current_order = None
                    self.action_state = "idle"
                    return False

        return False

    def _deliver_order(self, order: Order):
        """Entrega una orden y actualiza estadísticas."""
        time_used = self.game.game_time - order.accepted_at
        time_limit = order.duration_minutes * 60
        time_remaining = time_limit - time_used

        payout = order.payout
        bonus_multiplier = 1.0

        if time_remaining > time_limit * 0.66:
            bonus_multiplier += 0.1
            self.reputation += 5
            self.last_delivery_was_clean = True
        elif time_remaining >= 0:
            self.reputation += 2
            self.last_delivery_was_clean = True
        else:
            bonus_multiplier = 0.5
            self.reputation -= 3
            self.last_delivery_was_clean = False
            self.delivery_streak = 0

        if self.last_delivery_was_clean:
            self.delivery_streak += 1
            if self.delivery_streak >= 3:
                streak_bonus = min(0.05 * (self.delivery_streak // 3), 0.20)
                bonus_multiplier += streak_bonus

        final_payout = int(payout * bonus_multiplier)
        self.money += final_payout

        self.inventory.remove(order)
        order.status = "delivered"
        self.completed_orders.append(order)

        self.current_order = None
        self.current_target = None
        self.action_state = "idle"
        self.current_path = []
        self.path_index = 0

        print(f"CPU {self.player_id}: Orden {order.id} entregada - ${final_payout} (Rep: {self.reputation})")

        if self.money >= self.game.goal:
            print(f"🏆 CPU {self.player_id} HA GANADO! (${self.money})")
            self.game.victory = True
            self.game.game_over = True

    def _is_valid_move(self, pos: Position) -> bool:
        """Verifica si un movimiento es válido (NO ATRAVESAR EDIFICIOS)."""
        if not (0 <= pos.x < self.game.city_width and 0 <= pos.y < self.game.city_height):
            return False

        if pos.y >= len(self.game.tiles) or pos.x >= len(self.game.tiles[pos.y]):
            return False

        tile_char = self.game.tiles[pos.y][pos.x]
        tile_info = self.game.legend.get(tile_char, {})
        tile_type = tile_info.get('tipo', 'street')
        is_blocked = tile_info.get('blocked', False)

        return tile_type != 'building' and not is_blocked

    def _update_direction(self, target_pos: Position):
        """Actualiza la dirección visual basándose en el movimiento."""
        dx = target_pos.x - self.pos.x
        dy = target_pos.y - self.pos.y

        if abs(dx) > abs(dy):
            self.direction = "east" if dx > 0 else "west"
        else:
            self.direction = "south" if dy > 0 else "north"

    def _calculate_stamina_cost(self, pos: Position) -> float:
        """Calcula el costo de stamina para moverse a una posición."""
        base_cost = 2.0

        weather_penalty = self.game.weather_system.get_stamina_penalty()
        base_cost += weather_penalty

        current_weight = sum(o.weight for o in self.inventory)
        weight_ratio = current_weight / self.max_weight
        weight_penalty = weight_ratio * 0.5
        base_cost += weight_penalty

        return base_cost

    def _update_stamina_recovery(self, dt: float):
        """
        Actualiza la recuperación de stamina.
        MEJORADO: Recuperación rápida en parques, lenta fuera de ellos.
        """
        # Verificar posición válida
        if self.pos.y >= len(self.game.tiles) or self.pos.x >= len(self.game.tiles[self.pos.y]):
            # Recuperación pasiva mínima si no puede verificar el tile
            passive_recovery = 2.0 * dt  # 2 puntos por segundo
            self.stamina = min(self.max_stamina, self.stamina + passive_recovery)
            return

        tile_char = self.game.tiles[self.pos.y][self.pos.x]
        tile_info = self.game.legend.get(tile_char, {})

        # Obtener tipo y nombre del tile
        tile_type = tile_info.get('tipo', '').lower()
        tile_name = tile_info.get('name', '').lower()

        # Verificar si es parque (por tipo o nombre)
        is_park = (tile_type == 'park' or
                   'park' in tile_type or
                   'parque' in tile_name or
                   'parque' in tile_type)

        if is_park:
            # RECUPERACIÓN RÁPIDA EN PARQUES (igual que el jugador)
            recovery_rate = 15.0  # Puntos por segundo en parques
            recovery_amount = recovery_rate * dt
            old_stamina = self.stamina
            self.stamina = min(self.max_stamina, self.stamina + recovery_amount)

            # Log cada segundo aproximadamente
            if not hasattr(self, '_last_recovery_log'):
                self._last_recovery_log = 0

            import time
            current_time = time.time()
            if current_time - self._last_recovery_log >= 1.0:
                if self.stamina < self.max_stamina:
                    print(
                        f"CPU {self.player_id}: 🌳 Recuperando en PARQUE (+{recovery_rate}/s): {old_stamina:.1f} → {self.stamina:.1f}")
                self._last_recovery_log = current_time
        else:
            # Recuperación pasiva LENTA cuando NO está en parque
            passive_recovery_rate = 2.0  # 2 puntos por segundo (mucho más lento que en parque)
            recovery_amount = passive_recovery_rate * dt
            old_stamina = self.stamina
            self.stamina = min(self.max_stamina, self.stamina + recovery_amount)

            # Log ocasional solo si está bajo de stamina
            if not hasattr(self, '_last_passive_log'):
                self._last_passive_log = 0

            import time
            current_time = time.time()
            if current_time - self._last_passive_log >= 3.0 and self.stamina < 30:
                print(
                    f"CPU {self.player_id}: Recuperación pasiva (+{passive_recovery_rate}/s): {old_stamina:.1f} → {self.stamina:.1f}")
                self._last_passive_log = current_time

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

        if self.reputation < 20:
            print(f"💀 CPU {self.player_id} perdió por baja reputación")

    def get_available_orders(self) -> List[Order]:
        """Obtiene las órdenes disponibles para el CPU."""
        return [order for order in self.game.available_orders.items if order.status == "available"]

    def get_current_weight(self) -> int:
        """Retorna el peso actual del inventario."""
        return sum(o.weight for o in self.inventory)

    def has_capacity_for(self, order: Order) -> bool:
        """Verifica si hay capacidad para una orden."""
        return self.get_current_weight() + order.weight <= self.max_weight

    def get_weather_penalty(self) -> float:
        """Obtiene la penalización actual del clima."""
        return self.game.weather_system.get_stamina_penalty()

    def debug_pathfinding_graph(self):
        """
        DEBUG: Verifica que el grafo esté correctamente construido.
        """
        if not self.graph:
            print(f"⚠️ CPU {self.player_id}: Grafo no inicializado")
            return

        walkable_count = len(self.graph.adjacency_list)
        building_count = 0

        for y in range(self.game.city_height):
            for x in range(self.game.city_width):
                pos = Position(x, y)
                if not self.graph.is_walkable(pos):
                    building_count += 1

        print(
            f"✓ CPU {self.player_id}: Grafo construido - {walkable_count} posiciones transitables, {building_count} edificios/bloqueados")

        # Verificar que la posición actual está en el grafo
        if self.pos in self.graph.adjacency_list:
            neighbors = self.graph.get_neighbors(self.pos)
            print(
                f"✓ CPU {self.player_id}: Posición actual ({self.pos.x}, {self.pos.y}) tiene {len(neighbors)} vecinos")
        else:
            print(f"⚠️ CPU {self.player_id}: Posición actual ({self.pos.x}, {self.pos.y}) NO está en el grafo!")

    def is_low_stamina(self) -> bool:
        """
        Verifica si la stamina está críticamente baja.
        AJUSTADO: Umbral más bajo (15%) para ser más agresivo con el trabajo.
        """
        return self.stamina < 15.0  # 15% de 100

    def find_nearest_park(self) -> Optional[Position]:
        """
        Encuentra el parque más cercano.
        MEJORADO: Busca diferentes nombres/tipos de parques y es más flexible.
        """
        if not self.game.tiles or not self.game.legend:
            print(f"CPU {self.player_id}: ⚠️ No hay tiles o legend disponibles")
            return None

        nearest_park = None
        min_distance = float('inf')
        parks_found = 0

        for y in range(self.game.city_height):
            for x in range(self.game.city_width):
                if y >= len(self.game.tiles) or x >= len(self.game.tiles[y]):
                    continue

                tile_char = self.game.tiles[y][x]
                tile_info = self.game.legend.get(tile_char, {})

                # Buscar por tipo 'park' o nombre que contenga 'parque'
                tile_type = tile_info.get('tipo', '').lower()
                tile_name = tile_info.get('name', '').lower()

                is_park = (tile_type == 'park' or
                           'park' in tile_type or
                           'parque' in tile_name or
                           'parque' in tile_type)

                if is_park:
                    park_pos = Position(x, y)
                    parks_found += 1

                    # Verificar que la posición del parque es transitable
                    if not self._is_valid_move(park_pos):
                        print(f"CPU {self.player_id}: Parque encontrado en ({x}, {y}) pero NO es transitable")
                        continue

                    distance = abs(self.pos.x - x) + abs(self.pos.y - y)

                    if distance < min_distance:
                        min_distance = distance
                        nearest_park = park_pos

        print(f"CPU {self.player_id}: Parques encontrados en mapa: {parks_found}")

        if nearest_park:
            print(
                f"CPU {self.player_id}: ✅ Parque más cercano en ({nearest_park.x}, {nearest_park.y}), distancia: {min_distance}")
        else:
            if parks_found > 0:
                print(f"CPU {self.player_id}: ⚠️ Se encontraron {parks_found} parques pero ninguno es transitable")
            else:
                print(f"CPU {self.player_id}: ⚠️ NO hay parques en el mapa")

        return nearest_park

    def __repr__(self):
        """Representación en string del CPU Player."""
        return (f"CPUPlayer(id={self.player_id}, difficulty={self.difficulty}, "
                f"pos=({self.pos.x},{self.pos.y}), money=${self.money}, "
                f"reputation={self.reputation}, stamina={self.stamina:.1f})")

