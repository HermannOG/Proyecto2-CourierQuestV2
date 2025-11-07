"""
Estrategias de IA para el CPU Player
Implementa los tres niveles de dificultad: Fácil, Medio, Difícil
VERSIÓN FINAL CORREGIDA - Todas las interacciones funcionan correctamente
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
    """

    def __init__(self, game, player_id: str = "cpu_easy"):
        super().__init__(game, difficulty="easy", player_id=player_id)
        self.stuck_counter = 0
        self.max_stuck_attempts = 5
        self.random_target_timer = 0
        self.random_target_interval = 3.0

    def make_decision(self, dt: float):
        """Toma de decisiones aleatoria - VERSIÓN FINAL CORREGIDA."""
        self.random_target_timer += dt

        # PRIMERO: Intentar entregar si tiene paquetes en el inventario
        if self.inventory:
            # Verificar si está en alguna posición de dropoff
            for order in list(self.inventory):
                if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                    delivered = self.interact_at_position()
                    if delivered:
                        return  # Salir después de entregar

        # SEGUNDO: Si tiene orden activa, trabajar en ella
        if self.current_order:
            if self.action_state == "moving_to_pickup":
                # Si está en el pickup, intentar recoger
                if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                    picked_up = self.interact_at_position()
                    if picked_up:
                        return  # Salir después de recoger para procesar el nuevo estado
                else:
                    # Moverse hacia el pickup
                    self._random_move_towards(self.current_order.pickup)
                return  # Salir si está trabajando en pickup

            elif self.action_state == "moving_to_dropoff":
                if self.inventory:
                    order = self.inventory[0]
                    # Si está en el dropoff, intentar entregar
                    if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                        delivered = self.interact_at_position()
                        if delivered:
                            return  # Salir después de entregar
                    else:
                        # Moverse hacia el dropoff
                        self._random_move_towards(order.dropoff)
                return  # Salir si está trabajando en dropoff

        # TERCERO: Si no tiene orden, elegir una nueva
        if self.random_target_timer >= self.random_target_interval:
            self._choose_random_order()
            self.random_target_timer = 0

        # CUARTO: Si aún no tiene orden, caminar aleatoriamente
        if not self.current_order:
            self._random_walk()

    def _choose_random_order(self):
        """Elige una orden disponible al azar."""
        available = self.get_available_orders()

        if not available:
            return

        valid_orders = []
        current_weight = self.get_current_weight()

        for order in available:
            if current_weight + order.weight <= self.max_weight:
                valid_orders.append(order)

        if valid_orders:
            chosen_order = random.choice(valid_orders)
            self.current_order = chosen_order
            self.current_target = chosen_order.pickup
            self.action_state = "moving_to_pickup"

    def _random_move_towards(self, target: Position):
        """Movimiento semi-aleatorio hacia el objetivo."""
        if random.random() < 0.7:
            self._greedy_move_towards(target)
        else:
            self._random_walk()

    def _random_walk(self):
        """Movimiento completamente aleatorio."""
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

    def _greedy_move_towards(self, target: Position):
        """Movimiento greedy hacia el objetivo."""
        best_move = None
        best_distance = abs(target.x - self.pos.x) + abs(target.y - self.pos.y)

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

        if best_move:
            self.execute_move(best_move, 0.016)


# ============================================================================
# NIVEL MEDIO - BÚSQUEDA GREEDY CON HEURÍSTICAS
# ============================================================================

class MediumAI(CPUPlayer):
    """
    Nivel Medio: Evalúa movimientos con heurísticas
    score = α*payout - β*distance - γ*weather_penalty
    """

    def __init__(self, game, player_id: str = "cpu_medium"):
        super().__init__(game, difficulty="medium", player_id=player_id)
        self.look_ahead_depth = 2
        self.recalculation_interval = 2.0
        self.recalculation_timer = 0

    def make_decision(self, dt: float):
        """Toma de decisiones con evaluación heurística - VERSIÓN FINAL CORREGIDA."""
        self.recalculation_timer += dt

        # Verificar si necesita recuperar stamina
        if self.is_low_stamina():
            self._move_to_nearest_park()
            return

        # PRIMERO: Intentar entregar si tiene paquetes
        if self.inventory:
            for order in list(self.inventory):
                if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                    delivered = self.interact_at_position()
                    if delivered:
                        return  # Salir después de entregar

        # SEGUNDO: Si tiene orden actual, seguir con ella
        if self.current_order:
            if self.action_state == "moving_to_pickup":
                # Si está en el pickup, intentar recoger
                if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                    picked_up = self.interact_at_position()
                    if picked_up:
                        return  # Salir después de recoger para procesar el nuevo estado
                else:
                    # Moverse hacia el pickup
                    self._greedy_move_towards(self.current_order.pickup)
                return  # Salir si está trabajando en pickup

            elif self.action_state == "moving_to_dropoff" and self.inventory:
                order = self.inventory[0]
                # Si está en el dropoff, intentar entregar
                if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                    delivered = self.interact_at_position()
                    if delivered:
                        return  # Salir después de entregar
                else:
                    # Moverse hacia el dropoff
                    self._greedy_move_towards(order.dropoff)
                return  # Salir si está trabajando en dropoff

        # TERCERO: Evaluar y elegir la mejor orden
        if self.recalculation_timer >= self.recalculation_interval:
            self._evaluate_and_choose_best_order()
            self.recalculation_timer = 0

    def _evaluate_and_choose_best_order(self):
        """Evalúa y elige la mejor orden según score."""
        available = self.get_available_orders()

        if not available:
            return

        best_order = None
        best_score = -float('inf')
        current_weight = self.get_current_weight()

        for order in available:
            if current_weight + order.weight > self.max_weight:
                continue

            score = self._calculate_order_score(order)

            if score > best_score:
                best_score = score
                best_order = order

        if best_order:
            self.current_order = best_order
            self.current_target = best_order.pickup
            self.action_state = "moving_to_pickup"
            print(f"CPU {self.player_id}: Eligió orden {best_order.id} (Score: {best_score:.2f})")

    def _calculate_order_score(self, order: Order) -> float:
        """Calcula score: α*payout - β*distance - γ*weather_penalty"""
        alpha = 1.5
        payout_score = alpha * order.payout

        beta = 2.0
        distance_to_pickup = abs(self.pos.x - order.pickup.x) + abs(self.pos.y - order.pickup.y)
        distance_cost = beta * distance_to_pickup

        gamma = 10.0
        weather_penalty = gamma * self.game.weather_system.get_stamina_penalty()

        priority_bonus = order.priority * 20.0

        total_score = payout_score - distance_cost - weather_penalty + priority_bonus

        return total_score

    def _greedy_move_towards(self, target: Position):
        """Movimiento greedy: reduce distancia Manhattan."""
        best_move = None
        best_distance = abs(target.x - self.pos.x) + abs(target.y - self.pos.y)

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

        if best_move:
            success = self.execute_move(best_move, 0.016)
            if not success:
                print(f"CPU {self.player_id}: Movimiento falló")

    def _move_to_nearest_park(self):
        """Mueve hacia el parque más cercano."""
        nearest_park = self.find_nearest_park()

        if nearest_park:
            if self.pos.x == nearest_park.x and self.pos.y == nearest_park.y:
                return
            self._greedy_move_towards(nearest_park)


# ============================================================================
# NIVEL DIFÍCIL - ALGORITMOS DE GRAFOS (A* + TSP) CON ESTRATEGIA DE DESCANSO
# ============================================================================

# ============================================================================
# NIVEL DIFÍCIL - ALGORITMOS DE GRAFOS (A* + TSP) CON MEJOR PATHFINDING
# ============================================================================

class HardAI(CPUPlayer):
    """
    Nivel Difícil: Usa A* y TSP
    - A* para pathfinding óptimo (rodea edificios)
    - Replanificación dinámica por clima
    - TSP para secuenciar entregas
    - MEJORADO: Mejor manejo de colisiones y pathfinding robusto
    """

    def __init__(self, game, player_id: str = "cpu_hard"):
        super().__init__(game, difficulty="hard", player_id=player_id)
        self.replan_interval = 5.0
        self.replan_timer = 0
        self.current_path = []
        self.path_index = 0
        self.orders_sequence = []
        self.stuck_counter = 0
        self.max_stuck = 10

        # NUEVO: Parámetros para estrategia de descanso
        self.rest_strategy_threshold = 40.0
        self.min_park_distance_benefit = 3

    def make_decision(self, dt: float):
        """
        Toma de decisiones con A* y replanificación.
        MEJORADO: Incluye decisión estratégica de descanso preventivo.
        """
        self.replan_timer += dt

        # ESTRATEGIA INTELIGENTE DE DESCANSO
        if self._should_rest_strategically():
            if not self.current_path or self.current_target != self.find_nearest_park():
                print(f"CPU {self.player_id}: Decisión estratégica de descanso (stamina: {self.stamina:.1f})")
                self._plan_rest_route()
            self._follow_current_path()
            return

        # Recuperar stamina si está CRÍTICAMENTE baja
        if self.is_low_stamina():
            if not self.current_path or self.current_target != self.find_nearest_park():
                print(f"CPU {self.player_id}: Descanso urgente (stamina: {self.stamina:.1f})")
                self._plan_rest_route()
            self._follow_current_path()
            return

        # PRIMERO: Intentar entregar si tiene paquetes
        if self.inventory:
            for order in list(self.inventory):
                if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                    delivered = self.interact_at_position()
                    if delivered:
                        self.current_path = []
                        self.path_index = 0
                        return

        # SEGUNDO: Seguir camino si existe
        if self.current_path and self.path_index < len(self.current_path):
            self._follow_current_path()
            return

        # TERCERO: Si tiene orden pero sin camino, planear ruta
        if self.current_order:
            if self.action_state == "moving_to_pickup":
                if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                    picked_up = self.interact_at_position()
                    if picked_up:
                        self.current_path = []
                        self.path_index = 0
                        return
                else:
                    self._calculate_optimal_path(self.current_order.pickup)

            elif self.action_state == "moving_to_dropoff" and self.inventory:
                if self.pos.x == self.inventory[0].dropoff.x and self.pos.y == self.inventory[0].dropoff.y:
                    delivered = self.interact_at_position()
                    if delivered:
                        self.current_path = []
                        self.path_index = 0
                        return
                else:
                    self._calculate_optimal_path(self.inventory[0].dropoff)
            return

        # CUARTO: Replanificar secuencia óptima
        if self.replan_timer >= self.replan_interval or not self.current_order:
            self._plan_optimal_delivery_sequence()
            self.replan_timer = 0

    def _should_rest_strategically(self) -> bool:
        """
        NUEVO: Determina si es estratégicamente beneficioso descansar ahora.
        """
        if self.stamina > self.rest_strategy_threshold or self.is_low_stamina():
            return False

        nearest_park = self.find_nearest_park()
        if not nearest_park:
            return False

        park_distance = abs(self.pos.x - nearest_park.x) + abs(self.pos.y - nearest_park.y)

        if park_distance > 10:
            return False

        stamina_needed = self._estimate_stamina_needed_for_current_orders()
        weather_penalty = self.game.weather_system.get_stamina_penalty()
        stamina_after_park_trip = self.stamina - (park_distance * 0.5)

        if stamina_after_park_trip < stamina_needed:
            return True

        if weather_penalty > 1.5 and park_distance <= self.min_park_distance_benefit:
            return True

        if park_distance <= 2 and self.stamina < 50.0:
            return True

        return False

    def _estimate_stamina_needed_for_current_orders(self) -> float:
        """
        NUEVO: Estima cuánta stamina se necesita para completar las órdenes actuales.
        """
        stamina_estimate = 0.0

        if self.current_order:
            if self.action_state == "moving_to_pickup":
                distance_to_pickup = abs(self.pos.x - self.current_order.pickup.x) + \
                                     abs(self.pos.y - self.current_order.pickup.y)
                distance_pickup_to_dropoff = abs(self.current_order.pickup.x - self.current_order.dropoff.x) + \
                                             abs(self.current_order.pickup.y - self.current_order.dropoff.y)
                stamina_estimate += (distance_to_pickup + distance_pickup_to_dropoff) * 0.5

        if self.inventory:
            for order in self.inventory:
                distance_to_dropoff = abs(self.pos.x - order.dropoff.x) + \
                                      abs(self.pos.y - order.dropoff.y)
                stamina_estimate += distance_to_dropoff * 0.5

        stamina_estimate *= 1.2
        weather_penalty = self.game.weather_system.get_stamina_penalty()
        stamina_estimate *= weather_penalty

        return stamina_estimate

    def _calculate_optimal_path(self, target: Position):
        """
        Calcula camino óptimo con A* (rodea edificios).
        MEJORADO: Mejor validación y manejo de casos edge.
        """
        if not self.pathfinder:
            self.current_target = target
            self._greedy_move_towards_safe(target)
            return

        # VALIDACIÓN: Si el target es un edificio, encontrar posición caminable cercana
        if not self._is_valid_move(target):
            print(f"CPU {self.player_id}: Target ({target.x}, {target.y}) no es caminable, buscando posición cercana")
            walkable_target = self.pathfinder.get_closest_walkable_position(target)
            if walkable_target:
                target = walkable_target
                print(f"CPU {self.player_id}: Usando target ajustado ({target.x}, {target.y})")
            else:
                print(f"CPU {self.player_id}: No se encontró posición caminable cercana, usando greedy")
                self.current_target = target
                self._greedy_move_towards_safe(target)
                return

        # Si ya está en el target, no calcular camino
        if self.pos.x == target.x and self.pos.y == target.y:
            self.current_path = []
            self.path_index = 0
            self.current_target = target
            return

        weather_penalty = self.game.weather_system.get_stamina_penalty()
        path = self.pathfinder.a_star(self.pos, target, weather_penalty)

        if path and len(path) > 1:
            # Validar que el camino no tiene saltos
            valid_path = self._validate_path(path)

            if valid_path:
                self.current_path = path[1:]
                self.path_index = 0
                self.current_target = target
                self.stuck_counter = 0
                print(f"CPU {self.player_id}: Ruta A* calculada ({len(self.current_path)} pasos)")
            else:
                print(f"CPU {self.player_id}: Camino A* inválido, usando greedy seguro")
                self.current_path = []
                self.current_target = target
                self._greedy_move_towards_safe(target)
        else:
            self.current_path = []
            self.current_target = target
            print(f"CPU {self.player_id}: A* falló, usando greedy seguro")
            self._greedy_move_towards_safe(target)

    def _validate_path(self, path: List[Position]) -> bool:
        """
        NUEVO: Valida que un camino no tenga saltos ni posiciones inválidas.
        """
        if not path or len(path) < 2:
            return True

        for i in range(len(path) - 1):
            current = path[i]
            next_pos = path[i + 1]

            distance = abs(next_pos.x - current.x) + abs(next_pos.y - current.y)
            if distance > 1:
                print(
                    f"CPU {self.player_id}: Camino tiene salto entre ({current.x},{current.y}) y ({next_pos.x},{next_pos.y})")
                return False

            if not self._is_valid_move(next_pos):
                print(f"CPU {self.player_id}: Camino contiene posición inválida ({next_pos.x},{next_pos.y})")
                return False

        return True

    def _follow_current_path(self):
        """
        Sigue el camino planificado con validación robusta.
        MEJORADO: Mejor manejo cuando el camino se vuelve inválido.
        """
        if not self.current_path or self.path_index >= len(self.current_path):
            self.current_path = []
            self.path_index = 0
            return

        next_pos = self.current_path[self.path_index]

        if self.pos.x == next_pos.x and self.pos.y == next_pos.y:
            self.path_index += 1
            return

        # VALIDACIÓN: Verificar que el próximo movimiento es adyacente
        distance = abs(next_pos.x - self.pos.x) + abs(next_pos.y - self.pos.y)
        if distance > 1:
            print(f"CPU {self.player_id}: Camino con salto inválido detectado, replanificando")
            self.current_path = []
            self.path_index = 0
            self.stuck_counter = 0
            if self.current_target:
                self._calculate_optimal_path(self.current_target)
            return

        # VALIDACIÓN: Re-verificar que la posición es válida antes de moverse
        if not self._is_valid_move(next_pos):
            print(
                f"CPU {self.player_id}: Posición del camino ya no es válida ({next_pos.x}, {next_pos.y}), replanificando")
            self.current_path = []
            self.path_index = 0
            self.stuck_counter = 0
            if self.current_target:
                self._calculate_optimal_path(self.current_target)
            return

        if self.execute_move(next_pos, 0.016):
            self.path_index += 1
            self.stuck_counter = 0

            if self.path_index >= len(self.current_path):
                self.current_path = []
                self.path_index = 0
        else:
            self.stuck_counter += 1

            if self.stuck_counter >= 3:
                print(f"CPU {self.player_id}: Atascado después de {self.stuck_counter} intentos, replanificando")
                self.current_path = []
                self.path_index = 0
                self.stuck_counter = 0
                if self.current_target:
                    self._calculate_optimal_path(self.current_target)

    def _plan_rest_route(self):
        """Planifica ruta al parque con A*."""
        nearest_park = self.find_nearest_park()

        if nearest_park:
            self._calculate_optimal_path(nearest_park)

    def _plan_optimal_delivery_sequence(self):
        """Planifica secuencia con TSP."""
        available = self.get_available_orders()

        if not available:
            return

        valid_orders = []
        current_weight = self.get_current_weight()

        for order in available:
            if current_weight + order.weight <= self.max_weight:
                score = self._calculate_order_score(order)
                valid_orders.append((order, score))

        if not valid_orders:
            return

        valid_orders.sort(key=lambda x: x[1], reverse=True)
        top_orders = [order for order, score in valid_orders[:min(5, len(valid_orders))]]

        if self.tsp_solver and len(top_orders) > 1:
            optimized_sequence = self._optimize_delivery_sequence(top_orders)
            if optimized_sequence:
                top_orders = optimized_sequence

        if top_orders:
            self.current_order = top_orders[0]
            self.orders_sequence = top_orders[1:]
            self.action_state = "moving_to_pickup"
            self._calculate_optimal_path(self.current_order.pickup)

    def _optimize_delivery_sequence(self, orders: List[Order]) -> List[Order]:
        """Optimiza secuencia con TSP."""
        if not orders or not self.tsp_solver:
            return orders

        pickup_positions = [o.pickup for o in orders]
        optimal_route = self.tsp_solver.nearest_neighbor(self.pos, pickup_positions)

        ordered_orders = []
        for pos in optimal_route:
            for order in orders:
                if order.pickup.x == pos.x and order.pickup.y == pos.y and order not in ordered_orders:
                    ordered_orders.append(order)
                    break

        return ordered_orders

    def _calculate_order_score(self, order: Order) -> float:
        """
        Calcula score de orden.
        MEJORADO: Considera si tendrá suficiente stamina para completarla.
        """
        alpha = 1.5
        payout_score = alpha * order.payout

        beta = 2.0
        distance_to_pickup = abs(self.pos.x - order.pickup.x) + abs(self.pos.y - order.pickup.y)
        distance_pickup_to_dropoff = abs(order.pickup.x - order.dropoff.x) + \
                                     abs(order.pickup.y - order.dropoff.y)
        total_distance = distance_to_pickup + distance_pickup_to_dropoff
        distance_cost = beta * total_distance

        gamma = 10.0
        weather_penalty = gamma * self.game.weather_system.get_stamina_penalty()

        priority_bonus = order.priority * 20.0

        # Penalización si no tiene suficiente stamina
        stamina_needed = total_distance * 0.5 * self.game.weather_system.get_stamina_penalty()
        if self.stamina < stamina_needed:
            stamina_penalty = -50.0
        else:
            stamina_penalty = 0.0

        total_score = payout_score - distance_cost - weather_penalty + priority_bonus + stamina_penalty

        return total_score

    def _greedy_move_towards_safe(self, target: Position):
        """
        NUEVO: Movimiento greedy MEJORADO con mejor evitación de edificios.
        """
        current_distance = abs(target.x - self.pos.x) + abs(target.y - self.pos.y)

        moves = []

        directions = [
            Position(self.pos.x + 1, self.pos.y),
            Position(self.pos.x - 1, self.pos.y),
            Position(self.pos.x, self.pos.y + 1),
            Position(self.pos.x, self.pos.y - 1)
        ]

        for direction in directions:
            if not self._is_valid_move(direction):
                continue

            new_distance = abs(target.x - direction.x) + abs(target.y - direction.y)
            safety_bonus = self._calculate_safety_score(direction)
            score = -new_distance + (safety_bonus * 0.5)

            moves.append((direction, score, new_distance))

        if not moves:
            print(f"CPU {self.player_id}: Sin movimientos válidos disponibles")
            self.stuck_counter += 1
            return

        moves.sort(key=lambda x: x[1], reverse=True)
        best_move, best_score, new_distance = moves[0]

        if new_distance <= current_distance or best_score > 0:
            success = self.execute_move(best_move, 0.016)
            if not success:
                print(f"CPU {self.player_id}: Movimiento greedy falló")
                self.stuck_counter += 1
        else:
            print(f"CPU {self.player_id}: No puede acercarse al objetivo, buscando ruta alternativa")
            self.stuck_counter += 1

    def _calculate_safety_score(self, pos: Position) -> float:
        """
        NUEVO: Calcula un score de seguridad para una posición.
        """
        if not self.game.tiles or not self.game.legend:
            return 2.0

        safety_score = 0.0

        adjacent_positions = [
            Position(pos.x + 1, pos.y),
            Position(pos.x - 1, pos.y),
            Position(pos.x, pos.y + 1),
            Position(pos.x, pos.y - 1)
        ]

        for adj_pos in adjacent_positions:
            if self._is_valid_move(adj_pos):
                safety_score += 1.0

        return safety_score

    def _greedy_move_towards(self, target: Position):
        """
        Fallback greedy si A* falla.
        REDIRIGE al método seguro mejorado.
        """
        self._greedy_move_towards_safe(target)


# ============================================================================
# FACTORY
# ============================================================================

def create_cpu_player(game, difficulty: str, player_id: str = None) -> CPUPlayer:
    """Factory para crear CPU Player según dificultad."""
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