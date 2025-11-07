"""
Estrategias de IA para el CPU Player
Implementa los tres niveles de dificultad: Fácil, Medio, Difícil
"""

import random
from typing import List, Optional, Tuple
from collections import deque

from systems.cpu_player import CPUPlayer
from models.order import Order, Position


# ============================================================================
# NIVEL FÁCIL - MOVIMIENTOS ALEATORIOS (RANDOM WALK)
# ============================================================================

class EasyAI(CPUPlayer):
    """
    Nivel Fácil: Toma decisiones aleatorias
    - Elige órdenes al azar
    - Se mueve en direcciones aleatorias
    - Usa colas simples para gestión
    """

    def __init__(self, game, player_id: str = "cpu_easy"):
        super().__init__(game, difficulty="easy", player_id=player_id)
        self.stuck_counter = 0  # Contador para detectar cuando está atascado
        self.max_stuck_attempts = 5
        self.random_target_timer = 0
        self.random_target_interval = 3.0  # Cambiar objetivo cada 3 segundos

    def make_decision(self, dt: float):
        """
        Toma de decisiones aleatoria.
        """
        self.random_target_timer += dt

        # Estado 1: Entregar si está en el dropoff
        if self.inventory:
            self.interact_at_position()

        # Estado 2: Si tiene una orden, intentar ir al pickup o dropoff
        if self.current_order:
            if self.action_state == "moving_to_pickup":
                # Intentar llegar al pickup
                if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                    self.interact_at_position()
                else:
                    self._random_move_towards(self.current_order.pickup)
            elif self.action_state == "moving_to_dropoff":
                # Intentar llegar al dropoff
                if self.inventory:
                    order = self.inventory[0]
                    if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                        self.interact_at_position()
                    else:
                        self._random_move_towards(order.dropoff)
        else:
            # Estado 3: No tiene orden, elegir una aleatoriamente
            if self.random_target_timer >= self.random_target_interval:
                self._choose_random_order()
                self.random_target_timer = 0

            # Movimiento aleatorio si no tiene objetivo claro
            if not self.current_order:
                self._random_walk()

    def _choose_random_order(self):
        """Elige una orden disponible al azar."""
        available = self.get_available_orders()

        if not available:
            return

        # Filtrar órdenes que caben en la capacidad
        valid_orders = [o for o in available if self.has_capacity_for(o)]

        if valid_orders:
            # Elegir una al azar
            order = random.choice(valid_orders)
            self.current_order = order
            self.current_target = order.pickup
            self.action_state = "moving_to_pickup"
            print(f"CPU {self.player_id}: Eligió orden {order.id} (aleatorio)")

    def _random_move_towards(self, target: Position):
        """
        Se mueve en dirección general al objetivo pero con aleatoriedad.

        Args:
            target: Posición objetivo
        """
        # Calcular dirección general
        dx = target.x - self.pos.x
        dy = target.y - self.pos.y

        # Lista de direcciones posibles
        possible_moves = []

        # Priorizar movimientos hacia el objetivo (70% de probabilidad)
        if dx != 0 or dy != 0:
            if abs(dx) > abs(dy):
                # Horizontal más importante
                if dx > 0:
                    possible_moves.extend([Position(self.pos.x + 1, self.pos.y)] * 7)
                else:
                    possible_moves.extend([Position(self.pos.x - 1, self.pos.y)] * 7)
            else:
                # Vertical más importante
                if dy > 0:
                    possible_moves.extend([Position(self.pos.x, self.pos.y + 1)] * 7)
                else:
                    possible_moves.extend([Position(self.pos.x, self.pos.y - 1)] * 7)

        # Agregar movimientos aleatorios (30% de probabilidad)
        all_directions = [
            Position(self.pos.x + 1, self.pos.y),
            Position(self.pos.x - 1, self.pos.y),
            Position(self.pos.x, self.pos.y + 1),
            Position(self.pos.x, self.pos.y - 1)
        ]
        possible_moves.extend(all_directions * 3)

        # Intentar movimientos hasta encontrar uno válido
        random.shuffle(possible_moves)
        for move in possible_moves:
            if self._is_valid_move(move):
                if self.execute_move(move, 0.016):
                    self.stuck_counter = 0
                    return

        # Si está atascado, cancelar objetivo
        self.stuck_counter += 1
        if self.stuck_counter >= self.max_stuck_attempts:
            print(f"CPU {self.player_id}: Atascado, cambiando de plan")
            self.current_order = None
            self.action_state = "idle"
            self.stuck_counter = 0

    def _random_walk(self):
        """Camina en una dirección completamente aleatoria."""
        directions = [
            Position(self.pos.x + 1, self.pos.y),
            Position(self.pos.x - 1, self.pos.y),
            Position(self.pos.x, self.pos.y + 1),
            Position(self.pos.x, self.pos.y - 1)
        ]

        random.shuffle(directions)

        for direction in directions:
            if self._is_valid_move(direction):
                self.execute_move(direction, 0.016)
                break


# ============================================================================
# NIVEL MEDIO - BÚSQUEDA GREEDY CON HEURÍSTICAS
# ============================================================================

class MediumAI(CPUPlayer):
    """
    Nivel Medio: Evalúa movimientos futuros con heurísticas
    - Calcula scores para cada orden basándose en payout, distancia y clima
    - Usa búsqueda greedy para elegir la mejor acción
    - Planifica 2-3 movimientos por adelantado
    """

    def __init__(self, game, player_id: str = "cpu_medium"):
        super().__init__(game, difficulty="medium", player_id=player_id)
        self.look_ahead_depth = 2  # Horizonte de planificación
        self.recalculation_interval = 2.0
        self.recalculation_timer = 0

    def make_decision(self, dt: float):
        """
        Toma de decisiones usando evaluación heurística.
        """
        self.recalculation_timer += dt

        # Verificar si necesita recuperar stamina
        if self.is_low_stamina():
            self._move_to_nearest_park()
            return

        # Estado 1: Entregar si está en el dropoff
        if self.inventory:
            self.interact_at_position()

        # Estado 2: Si tiene orden actual, seguir con ella
        if self.current_order:
            if self.action_state == "moving_to_pickup":
                if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                    self.interact_at_position()
                else:
                    self._greedy_move_towards(self.current_order.pickup)
            elif self.action_state == "moving_to_dropoff" and self.inventory:
                order = self.inventory[0]
                if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                    self.interact_at_position()
                else:
                    self._greedy_move_towards(order.dropoff)
        else:
            # Estado 3: Evaluar y elegir la mejor orden
            if self.recalculation_timer >= self.recalculation_interval:
                self._evaluate_and_choose_best_order()
                self.recalculation_timer = 0

    def _evaluate_and_choose_best_order(self):
        """
        Evalúa todas las órdenes disponibles y elige la mejor según score.
        """
        available = self.get_available_orders()

        if not available:
            return

        best_order = None
        best_score = -float('inf')

        for order in available:
            if not self.has_capacity_for(order):
                continue

            score = self._calculate_order_score(order)

            if score > best_score:
                best_score = score
                best_order = order

        if best_order:
            self.current_order = best_order
            self.current_target = best_order.pickup
            self.action_state = "moving_to_pickup"
            print(f"CPU {self.player_id}: Eligió orden {best_order.id} (score: {best_score:.2f})")

    def _calculate_order_score(self, order: Order) -> float:
        """
        Calcula el score de una orden usando heurísticas.

        Score = α*(payout) - β*(distance) - γ*(weather_penalty) + δ*(urgency) + ε*(reputation)

        Args:
            order: Orden a evaluar

        Returns:
            Score de la orden (mayor es mejor)
        """
        # Distancia total (pickup + delivery)
        pickup_distance = abs(order.pickup.x - self.pos.x) + abs(order.pickup.y - self.pos.y)
        delivery_distance = abs(order.dropoff.x - order.pickup.x) + abs(order.dropoff.y - order.pickup.y)
        total_distance = pickup_distance + delivery_distance

        # Payout esperado
        expected_payout = order.payout

        # Factor de urgencia (basado en prioridad y tiempo)
        urgency = order.priority * 1.5
        time_left = order.duration_minutes * 60 - (self.game.game_time - order.created_at)
        if time_left < 120:  # Menos de 2 minutos
            urgency += 2.0

        # Penalización por clima
        weather_penalty = self.get_weather_penalty() * total_distance

        # Bonus por reputación potencial
        reputation_bonus = 0
        if time_left > order.duration_minutes * 60 * 0.7:
            reputation_bonus = 5

        # Calcular score con pesos balanceados
        alpha = 1.0   # Peso del payout
        beta = 10.0   # Peso de la distancia (penalización)
        gamma = 5.0   # Peso del clima (penalización)
        delta = 20.0  # Peso de la urgencia
        epsilon = 10.0  # Peso de la reputación

        score = (
            alpha * expected_payout -
            beta * total_distance -
            gamma * weather_penalty +
            delta * urgency +
            epsilon * reputation_bonus
        )

        return score

    def _greedy_move_towards(self, target: Position):
        """
        Movimiento greedy hacia un objetivo.
        Elige el movimiento que más reduce la distancia Manhattan.

        Args:
            target: Posición objetivo
        """
        best_move = None
        best_distance = abs(target.x - self.pos.x) + abs(target.y - self.pos.y)

        # Evaluar los 4 movimientos posibles
        directions = [
            Position(self.pos.x + 1, self.pos.y),
            Position(self.pos.x - 1, self.pos.y),
            Position(self.pos.x, self.pos.y + 1),
            Position(self.pos.x, self.pos.y - 1)
        ]

        for direction in directions:
            if not self._is_valid_move(direction):
                continue

            distance = abs(target.x - direction.x) + abs(target.y - direction.y)

            if distance < best_distance:
                best_distance = distance
                best_move = direction

        # Ejecutar el mejor movimiento
        if best_move:
            self.execute_move(best_move, 0.016)

    def _move_to_nearest_park(self):
        """Mueve al CPU hacia el parque más cercano para recuperar stamina."""
        nearest_park = self.find_nearest_park()

        if nearest_park:
            # Si ya está en un parque, quedarse quieto para recuperar
            if self.pos.x == nearest_park.x and self.pos.y == nearest_park.y:
                return

            # Moverse hacia el parque
            self._greedy_move_towards(nearest_park)


# ============================================================================
# NIVEL DIFÍCIL - ALGORITMOS DE GRAFOS (A* + TSP)
# ============================================================================

class HardAI(CPUPlayer):
    """
    Nivel Difícil: Usa algoritmos de grafos para optimización
    - A* para pathfinding óptimo
    - TSP aproximado para secuenciar entregas
    - Planificación dinámica considerando clima
    """

    def __init__(self, game, player_id: str = "cpu_hard"):
        super().__init__(game, difficulty="hard", player_id=player_id)
        self.replan_interval = 5.0
        self.replan_timer = 0
        self.current_path = []
        self.path_index = 0
        self.orders_sequence = []  # Secuencia optimizada de órdenes

    def make_decision(self, dt: float):
        """
        Toma de decisiones usando algoritmos de grafos.
        """
        # Inicializar pathfinding si no está listo
        if not self.pathfinder:
            self.initialize_pathfinding()
            return

        self.replan_timer += dt

        # Verificar si necesita recuperar stamina
        if self.is_low_stamina() and not self.inventory:
            self._plan_rest_route()
            self._follow_planned_path()
            return

        # Estado 1: Entregar si está en el dropoff
        if self.inventory:
            self.interact_at_position()

        # Estado 2: Seguir el plan actual si existe
        if self.current_path and self.path_index < len(self.current_path):
            self._follow_planned_path()
        else:
            # Estado 3: Replanificar ruta
            if self.replan_timer >= self.replan_interval or not self.current_order:
                self._replan_route()
                self.replan_timer = 0

    def _replan_route(self):
        """
        Replanifica la ruta óptima usando A* y TSP.
        """
        # Si tiene orden actual, continuar con ella
        if self.current_order and self.action_state == "moving_to_pickup":
            target = self.current_order.pickup
            self._calculate_optimal_path(target)
            return
        elif self.inventory:
            # Entregar lo que tiene primero
            target = self.inventory[0].dropoff
            self._calculate_optimal_path(target)
            return

        # Elegir nueva orden óptima
        available = self.get_available_orders()

        if not available:
            return

        # Filtrar órdenes válidas
        valid_orders = [o for o in available if self.has_capacity_for(o)]

        if not valid_orders:
            return

        # Evaluar y elegir la mejor orden usando A*
        best_order = self._find_optimal_order(valid_orders)

        if best_order:
            self.current_order = best_order
            self.current_target = best_order.pickup
            self.action_state = "moving_to_pickup"
            self._calculate_optimal_path(best_order.pickup)
            print(f"CPU {self.player_id}: Eligió orden {best_order.id} (A* optimal)")

    def _find_optimal_order(self, orders: List[Order]) -> Optional[Order]:
        """
        Encuentra la orden óptima considerando distancia real y beneficio.

        Args:
            orders: Lista de órdenes disponibles

        Returns:
            Mejor orden, o None
        """
        best_order = None
        best_value = -float('inf')

        weather_penalty = self.get_weather_penalty()

        for order in orders:
            # Calcular costo real del camino usando A*
            path_to_pickup = self.pathfinder.a_star(self.pos, order.pickup, weather_penalty)

            if not path_to_pickup:
                continue

            path_to_delivery = self.pathfinder.a_star(order.pickup, order.dropoff, weather_penalty)

            if not path_to_delivery:
                continue

            # Calcular valor: payout / (costo_total)
            total_cost = len(path_to_pickup) + len(path_to_delivery)
            urgency_factor = (order.priority + 1) * 1.5

            # Factor de tiempo
            time_left = order.duration_minutes * 60 - (self.game.game_time - order.created_at)
            time_factor = max(0.5, time_left / (order.duration_minutes * 60))

            value = (order.payout * urgency_factor * time_factor) / max(total_cost, 1)

            if value > best_value:
                best_value = value
                best_order = order

        return best_order

    def _calculate_optimal_path(self, target: Position):
        """
        Calcula el camino óptimo usando A*.

        Args:
            target: Posición objetivo
        """
        weather_penalty = self.get_weather_penalty()
        path = self.pathfinder.a_star(self.pos, target, weather_penalty)

        if path:
            self.current_path = path
            self.path_index = 0
            print(f"CPU {self.player_id}: Camino calculado ({len(path)} pasos)")
        else:
            # Si no hay camino, intentar con BFS simple
            path = self.pathfinder.bfs(self.pos, target)
            if path:
                self.current_path = path
                self.path_index = 0
            else:
                print(f"CPU {self.player_id}: No se encontró camino al objetivo")
                self.current_order = None
                self.action_state = "idle"

    def _follow_planned_path(self):
        """Sigue el camino planificado paso a paso."""
        if not self.current_path or self.path_index >= len(self.current_path):
            return

        next_pos = self.current_path[self.path_index]

        # Verificar si ya está en la siguiente posición
        if self.pos.x == next_pos.x and self.pos.y == next_pos.y:
            self.path_index += 1
            return

        # Intentar moverse a la siguiente posición
        if self.execute_move(next_pos, 0.016):
            self.path_index += 1

            # Si llegó al final del camino
            if self.path_index >= len(self.current_path):
                self.current_path = []
                self.path_index = 0

                # Intentar interactuar en el destino
                self.interact_at_position()

    def _plan_rest_route(self):
        """Planifica ruta al parque más cercano para descansar."""
        nearest_park = self.find_nearest_park()

        if nearest_park:
            self._calculate_optimal_path(nearest_park)

    def _optimize_delivery_sequence(self, orders: List[Order]) -> List[Order]:
        """
        Optimiza la secuencia de entregas usando TSP aproximado.

        Args:
            orders: Lista de órdenes a optimizar

        Returns:
            Lista ordenada de órdenes en secuencia óptima
        """
        if not orders or not self.tsp_solver:
            return orders

        # Extraer posiciones de pickup
        pickup_positions = [o.pickup for o in orders]

        # Resolver TSP para encontrar secuencia óptima
        optimal_route = self.tsp_solver.nearest_neighbor(self.pos, pickup_positions)

        # Reordenar órdenes según la ruta óptima
        ordered_orders = []
        for pos in optimal_route:
            for order in orders:
                if order.pickup.x == pos.x and order.pickup.y == pos.y and order not in ordered_orders:
                    ordered_orders.append(order)
                    break

        return ordered_orders


# ============================================================================
# FACTORY PARA CREAR INSTANCIAS DE AI
# ============================================================================

def create_cpu_player(game, difficulty: str, player_id: str = None) -> CPUPlayer:
    """
    Factory para crear instancias de CPU Player según dificultad.

    Args:
        game: Instancia del juego
        difficulty: Nivel de dificultad ("easy", "medium", "hard")
        player_id: Identificador del jugador (opcional)

    Returns:
        Instancia de CPUPlayer correspondiente

    Raises:
        ValueError: Si la dificultad no es válida
    """
    difficulty = difficulty.lower()

    if player_id is None:
        player_id = f"cpu_{difficulty}"

    if difficulty == "easy":
        return EasyAI(game, player_id)
    elif difficulty == "medium":
        return MediumAI(game, player_id)
    elif difficulty == "hard":
        return HardAI(game, player_id)
    else:
        raise ValueError(f"Dificultad inválida: {difficulty}. Use 'easy', 'medium' o 'hard'")
