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
        self.move_cooldown = 0.25
        self.decision_interval = 0.3

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
        # 70% de probabilidad de acercarse al objetivo
        # 30% de probabilidad de movimiento completamente aleatorio
        if random.random() < 0.75:
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

        # Para seguir caminos BFS (SOLO cuando se queda pegado)
        self.bfs_path = []
        self.bfs_path_index = 0

        # Detección de oscilación/bucle
        self.position_history = []
        self.max_history_length = 8
        self.oscillation_threshold = 3
        self.last_distance_to_target = None
        self.no_progress_counter = 0
        self.max_no_progress = 4

        # NUEVO: Sistema de descanso automático cuando stamina <= 10
        self.needs_rest = False  # Se activa cuando stamina llega a 10 o menos
        self.is_resting_medium = False  # Indica que está descansando en el parque
        self.rest_target = None  # Parque objetivo para descansar

    def make_decision(self, dt: float):
        """
        Toma de decisiones con evaluación heurística.

        Comportamiento según instrucciones:
        - Horizonte de anticipación pequeño (2-3 acciones por delante)
        - Evalúa movimientos potenciales con función de puntuación simple:
          score = α*(expected payout) - β*(distance cost) - γ*(weather penalty)
        - Selecciona el movimiento con la puntuación máxima
        - Cuando stamina <= 15, va automáticamente a un parque y espera
        - USA GREEDY como método principal
        """
        self.recalculation_timer += dt

        # ===== SISTEMA DE DESCANSO CUANDO STAMINA <= 10 =====

        # Verificar si necesita descansar (stamina llegó a 10 o menos)
        if self.stamina <= 15.0 and not self.needs_rest:
            print(f"CPU {self.player_id}: STAMINA BAJA ({self.stamina:.1f})! Buscando parque para descansar...")
            self.needs_rest = True
            self.is_resting_medium = False
            self.rest_target = None
            self.current_order = None
            self.current_target = None
            self.bfs_path = []
            self.bfs_path_index = 0

        if self.needs_rest:
            in_park = self._is_in_park()

            if in_park:
                if not self.is_resting_medium:
                    print(f"CPU {self.player_id}: Llegó al parque! Descansando...")
                    self.is_resting_medium = True

                if self.stamina >= 85.0:
                    print(f"CPU {self.player_id}: Stamina recargada completamente! Regresando al trabajo...")
                    self.needs_rest = False
                    self.is_resting_medium = False
                    self.rest_target = None
                else:
                    # Mostrar progreso cada cierto tiempo
                    if not hasattr(self, '_last_rest_message'):
                        self._last_rest_message = 0

                    import time
                    current_time = time.time()
                    if current_time - self._last_rest_message >= 3.0:
                        print(f"CPU {self.player_id}: Descansando en parque ({self.stamina:.1f}/100)")
                        self._last_rest_message = current_time
                    return
            else:
                # No está en parque, ir al más cercano usando GREEDY
                if not self.rest_target:
                    self.rest_target = self.find_nearest_park()
                    if self.rest_target:
                        print(
                            f"CPU {self.player_id}: Dirigiéndose al parque en ({self.rest_target.x}, {self.rest_target.y})")
                    else:
                        print(f"CPU {self.player_id}: No hay parques disponibles! Esperando recuperación natural...")
                        return

                # Moverse hacia el parque usando GREEDY (con BFS como fallback)
                if self.rest_target:
                    self._greedy_move_towards_safe(self.rest_target)
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
                    # Moverse hacia el pickup usando GREEDY (método principal)
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
                    # Moverse hacia el dropoff usando GREEDY (método principal)
                    self._greedy_move_towards(order.dropoff)
                return  # Salir si está trabajando en dropoff

        # TERCERO: Evaluar y elegir la mejor orden usando heurística
        if self.recalculation_timer >= self.recalculation_interval:
            self._evaluate_and_choose_best_order()
            self.recalculation_timer = 0

    def _evaluate_and_choose_best_order(self):
        """
        Evalúa y elige la mejor orden según score.

        Implementa la función de puntuación simple según instrucciones:
        score = α*(expected payout) - β*(distance cost) - γ*(weather penalty)

        Mantiene un horizonte de anticipación pequeño (2-3 acciones por delante).
        """
        available = self.get_available_orders()

        if not available:
            return

        # Filtrar por capacidad
        current_weight = self.get_current_weight()
        valid_orders = [
            order for order in available
            if current_weight + order.weight <= self.max_weight
        ]

        if not valid_orders:
            return

        best_order = None
        best_score = float('-inf')

        # Pesos para la función de puntuación (α, β, γ)
        alpha = 1.0
        beta = 0.5
        gamma = 1.0

        for order in valid_orders:
            # Componente 1: Pago esperado (expected payout)
            expected_payout = order.payout

            # Componente 2: Costo de distancia (distance cost)
            # Anticipación limitada: solo mira 2-3 pasos adelante
            distance_to_pickup = abs(self.pos.x - order.pickup.x) + abs(self.pos.y - order.pickup.y)
            distance_pickup_to_dropoff = abs(order.pickup.x - order.dropoff.x) + abs(order.pickup.y - order.dropoff.y)
            total_distance = distance_to_pickup + distance_pickup_to_dropoff
            distance_cost = total_distance

            # Componente 3: Penalización por clima (weather penalty)
            weather_penalty = self.game.weather_system.get_stamina_penalty()
            # Penalización mayor si el clima es adverso
            weather_cost = (weather_penalty - 1.0) * total_distance

            # Calcular score según la fórmula
            # score = α*(expected payout) - β*(distance cost) - γ*(weather penalty)
            score = (alpha * expected_payout) - (beta * distance_cost) - (gamma * weather_cost)

            # Seleccionar el movimiento con la puntuación máxima
            if score > best_score:
                best_score = score
                best_order = order

        # Asignar la mejor orden
        if best_order:
            self.current_order = best_order
            self.current_target = best_order.pickup
            self.action_state = "moving_to_pickup"

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
        """
        Movimiento GREEDY hacia el objetivo (MÉTODO PRINCIPAL).
        Evalúa movimientos con heurística simple: minimizar distancia Manhattan.
        Mantiene el horizonte de anticipación pequeño: evalúa solo movimientos inmediatos.

        BFS solo se usa como FALLBACK cuando detecta oscilación o falta de progreso.
        """
        # Reiniciar detección de oscilación si cambió el objetivo
        if not self.current_target or \
                (self.current_target.x != target.x or self.current_target.y != target.y):
            self.position_history = []
            self.no_progress_counter = 0
            self.last_distance_to_target = None

        self.current_target = target

        # Agregar posición actual al historial
        self.position_history.append((self.pos.x, self.pos.y))
        if len(self.position_history) > self.max_history_length:
            self.position_history.pop(0)

        # Detectar oscilación (cuando se queda pegado en bucle)
        if len(self.position_history) >= self.oscillation_threshold:
            position_counts = {}
            for pos in self.position_history:
                position_counts[pos] = position_counts.get(pos, 0) + 1

            for count in position_counts.values():
                if count >= self.oscillation_threshold:
                    print(f"CPU {self.player_id}: Oscilación detectada, usando BFS como fallback")
                    # FALLBACK: Usar BFS solo cuando se queda pegado
                    self._move_via_bfs(target)
                    return

        # Detectar falta de progreso (cuando no avanza)
        current_distance = abs(target.x - self.pos.x) + abs(target.y - self.pos.y)

        if self.last_distance_to_target is not None:
            if current_distance >= self.last_distance_to_target:
                self.no_progress_counter += 1
            else:
                self.no_progress_counter = 0

            if self.no_progress_counter >= self.max_no_progress:
                print(f"CPU {self.player_id}: Sin progreso detectado, usando BFS como fallback")
                # FALLBACK: Usar BFS solo cuando no progresa
                self._move_via_bfs(target)
                self.no_progress_counter = 0
                return

        self.last_distance_to_target = current_distance

        # ===== MOVIMIENTO GREEDY NORMAL (MÉTODO PRINCIPAL) =====

        best_move = None
        best_score = float('-inf')

        # Evaluar las 4 direcciones posibles (horizonte pequeño: solo 1 paso)
        directions = [
            Position(self.pos.x + 1, self.pos.y),  # Este
            Position(self.pos.x - 1, self.pos.y),  # Oeste
            Position(self.pos.x, self.pos.y + 1),  # Sur
            Position(self.pos.x, self.pos.y - 1)  # Norte
        ]

        for direction in directions:
            if not self._is_valid_move(direction):
                continue

            distance_to_goal = abs(target.x - direction.x) + abs(target.y - direction.y)

            position_penalty = 0
            if (direction.x, direction.y) in self.position_history[-3:]:
                position_penalty = 5

            # Score final: α*(-distance) - β*(weather_penalty) - γ*(position_penalty)
            weather_multiplier = self.game.weather_system.get_stamina_penalty()
            score = -distance_to_goal - (weather_multiplier - 1.0) * 2 - position_penalty

            # Seleccionar el movimiento con mejor score (puntuación máxima)
            if score > best_score:
                best_score = score
                best_move = direction

        # Ejecutar el mejor movimiento greedy
        if best_move:
            success = self.execute_move(best_move, 0.016)
            if not success:
                print(f"CPU {self.player_id}: Movimiento greedy falló, intentando otro")

    def _greedy_move_towards_safe(self, target: Position):
        """
        Versión segura de movimiento greedy con BFS como fallback.
        Útil cuando se dirige al parque para descansar.
        USA GREEDY como principal.
        """
        best_move = None
        best_score = float('-inf')

        directions = [
            Position(self.pos.x + 1, self.pos.y),
            Position(self.pos.x - 1, self.pos.y),
            Position(self.pos.x, self.pos.y + 1),
            Position(self.pos.x, self.pos.y - 1)
        ]

        for direction in directions:
            if not self._is_valid_move(direction):
                continue

            # Heurística simple: minimizar distancia
            distance = abs(target.x - direction.x) + abs(target.y - direction.y)
            score = -distance

            if score > best_score:
                best_score = score
                best_move = direction

        if best_move:
            success = self.execute_move(best_move, 0.016)
            if success:
                return

        print(f"CPU {self.player_id}: Greedy falló, usando BFS como fallback")
        self._move_via_bfs(target)

    def _add_to_position_history(self, pos: Position):
        """Añade una posición al historial."""
        self.position_history.append((pos.x, pos.y))

        if len(self.position_history) > self.max_history_length:
            self.position_history.pop(0)

    def _is_oscillating(self) -> bool:
        """
        Detecta si el CPU está oscilando entre las mismas posiciones.
        Retorna True si una posición aparece más de N veces en el historial.
        """
        if len(self.position_history) < 4:
            return False

        position_counts = {}
        for pos in self.position_history:
            position_counts[pos] = position_counts.get(pos, 0) + 1

        max_count = max(position_counts.values())
        return max_count >= self.oscillation_threshold

    def _get_visit_penalty(self, pos: Position) -> float:
        """
        Retorna una penalización basada en cuántas veces se ha visitado recientemente.
        """
        pos_tuple = (pos.x, pos.y)
        count = self.position_history.count(pos_tuple)

        # Penalización progresiva
        return count * 5.0

    def _is_in_park(self) -> bool:
        """
        Verifica si el CPU está actualmente en un parque.
            True si está en un parque, False en caso contrario
        """
        if self.pos.y >= len(self.game.tiles) or self.pos.x >= len(self.game.tiles[self.pos.y]):
            return False

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

        return is_park

    def _calculate_safety_score(self, pos: Position) -> float:
        """
        Calcula un score de seguridad basado en espacios abiertos adyacentes.
        Evita callejones sin salida y esquinas.
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

    def _move_via_bfs(self, target: Position):
        """
        Movimiento usando BFS SOLO COMO FALLBACK cuando el greedy falla.
        NO es el método principal de movimiento.
        """
        # Si no hay camino calculado o ya terminó
        if not self.bfs_path or self.bfs_path_index >= len(self.bfs_path):
            # Calcular nuevo camino BFS
            self.bfs_path = self._bfs_path(self.pos, target)
            self.bfs_path_index = 0

            if not self.bfs_path:
                return

        if self.bfs_path_index < len(self.bfs_path):
            next_pos = self.bfs_path[self.bfs_path_index]

            if self._is_valid_move(next_pos):
                distance = abs(next_pos.x - self.pos.x) + abs(next_pos.y - self.pos.y)
                if distance == 1:
                    success = self.execute_move(next_pos, 0.016)
                    if success:
                        self.bfs_path_index += 1
                    else:
                        # Si falló, recalcular camino
                        self.bfs_path = []
                        self.bfs_path_index = 0
                else:
                    # Camino inválido, recalcular
                    self.bfs_path = []
                    self.bfs_path_index = 0
            else:
                # Posición bloqueada, recalcular camino
                self.bfs_path = []
                self.bfs_path_index = 0

    def _bfs_path(self, start: Position, goal: Position) -> List[Position]:
        """
        BFS simple para encontrar camino (SOLO FALLBACK).
        """
        from collections import deque

        if start.x == goal.x and start.y == goal.y:
            return []

        visited = set()
        queue = deque([(start, [])])
        visited.add((start.x, start.y))

        while queue:
            current_pos, path = queue.popleft()

            neighbors = [
                Position(current_pos.x + 1, current_pos.y),
                Position(current_pos.x - 1, current_pos.y),
                Position(current_pos.x, current_pos.y + 1),
                Position(current_pos.x, current_pos.y - 1)
            ]

            for neighbor in neighbors:
                if neighbor.x == goal.x and neighbor.y == goal.y:
                    return path + [neighbor]

                if self._is_valid_move(neighbor) and (neighbor.x, neighbor.y) not in visited:
                    visited.add((neighbor.x, neighbor.y))
                    queue.append((neighbor, path + [neighbor]))

        return []  # No se encontró camino

    def _limited_bfs(self, target: Position, max_depth: int = 35) -> Optional[List[Position]]:
        """
        BFS limitado para encontrar un camino corto al objetivo.
        Útil cuando el camino directo está bloqueado pero hay rutas cercanas.
        """
        from collections import deque

        if not self._is_valid_move(self.pos):
            return None

        queue = deque([(self.pos, [self.pos])])
        visited = {(self.pos.x, self.pos.y)}

        directions = [
            (0, 1),  # Sur
            (0, -1),  # Norte
            (1, 0),  # Este
            (-1, 0)  # Oeste
        ]

        while queue:
            current_pos, path = queue.popleft()

            if len(path) > max_depth:
                continue

            # Si llegamos al objetivo
            if current_pos.x == target.x and current_pos.y == target.y:
                print(f"CPU {self.player_id}: ✓ BFS encontró camino de {len(path)} pasos")
                return path

            for dx, dy in directions:
                next_pos = Position(current_pos.x + dx, current_pos.y + dy)
                next_tuple = (next_pos.x, next_pos.y)

                if next_tuple not in visited and self._is_valid_move(next_pos):
                    visited.add(next_tuple)
                    new_path = path + [next_pos]
                    queue.append((next_pos, new_path))

        print(f"CPU {self.player_id}: ✗ BFS no encontró camino en {max_depth} pasos")
        return None


# ============================================================================
# NIVEL DIFÍCIL - ALGORITMOS DE GRAFOS (A* + TSP) CON ESTRATEGIA DE DESCANSO
# ============================================================================

class HardAI(CPUPlayer):
    """
    Nivel Difícil: Usa A* y TSP
    - A* para pathfinding óptimo (rodea edificios)
    - Replanificación dinámica por clima
    - TSP para secuenciar entregas
    - Manejo de colisiones y pathfinding robusto
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
        self.rest_strategy_threshold = 50.0
        self.min_park_distance_benefit = 3
        self.park_exit_attempts = 0
        self.max_park_exit_attempts = 5
        self.last_park_position = None

    def make_decision(self, dt: float):
        """
        Toma de decisiones con A* y replanificación.
        INCLUYE: Recolección oportunista de paquetes cercanos durante entregas.
        """
        self.replan_timer += dt

        if self.stamina < 2.1:
            if not hasattr(self, '_last_waiting_log'):
                self._last_waiting_log = 0

            import time
            current_time = time.time()
            if current_time - self._last_waiting_log >= 2.0:
                print(f"CPU {self.player_id}: ️ ESPERANDO recuperar stamina ({self.stamina:.1f}/100)")
                self._last_waiting_log = current_time
            return

        # ===== GESTIÓN DE DESCANSO EN PARQUE =====
        if not hasattr(self, '_is_resting'):
            self._is_resting = False

        in_park = self._is_in_park()

        # Si está descansando y todavía no tiene suficiente stamina, seguir descansando
        if self._is_resting and in_park and self.stamina < 100.0:
            print(f"CPU {self.player_id}: Descansando en parque ({self.stamina:.1f}/100)")
            return

        # Si ya tiene suficiente stamina o no está en parque, dejar de descansar
        if self._is_resting and (self.stamina >= 100.0 or not in_park):
            print(f"CPU {self.player_id}: Terminó de descansar ({self.stamina:.1f})! Continuando tareas")
            self._is_resting = False
            self.current_path = []
            self.path_index = 0
            self.current_target = None

        # ===== SOLO IR AL PARQUE SI STAMINA < 15 Y NO ESTÁ DESCANSANDO =====
        if self.stamina < 15.0 and not self._is_resting:
            if not in_park:
                nearest_park = self.find_nearest_park()

                if nearest_park:
                    has_park_route = (self.current_target and
                                      self.current_target.x == nearest_park.x and
                                      self.current_target.y == nearest_park.y)

                    if not has_park_route:
                        print(f"CPU {self.player_id}: ⚡ STAMINA CRÍTICA ({self.stamina:.1f}) - Yendo a parque")
                        self._plan_rest_route()

                    self._follow_current_path()
                    return
                else:
                    print(f"CPU {self.player_id}: ️ Stamina crítica pero sin parques ({self.stamina:.1f})")
                    return
            else:
                print(f"CPU {self.player_id}: Llegó al parque, iniciando descanso ({self.stamina:.1f})")
                self._is_resting = True
                self.current_path = []
                self.path_index = 0
                self.current_target = None
                return

        # ===== MANEJO DE ESTADO OPORTUNISTA =====
        if self._handle_opportunistic_state():
            return

        # ===== FLUJO NORMAL DE TRABAJO =====

        # PRIMERO: Intentar entregar si tiene paquetes
        if self.inventory:
            for order in list(self.inventory):
                if self.pos.x == order.dropoff.x and self.pos.y == order.dropoff.y:
                    delivered = self.interact_at_position()
                    if delivered:
                        self.current_path = []
                        self.path_index = 0
                        self.current_order = None

                        if self.inventory:
                            next_dropoff = self.inventory[0].dropoff
                            print(f"CPU {self.player_id}: Siguiente entrega en ({next_dropoff.x}, {next_dropoff.y})")
                            self._calculate_optimal_path(next_dropoff)
                        return
                else:
                    if self._check_opportunistic_pickup():
                        return

                    if not self.current_target or \
                            self.current_target.x != order.dropoff.x or \
                            self.current_target.y != order.dropoff.y:
                        print(f"CPU {self.player_id}: Calculando ruta a dropoff ({order.dropoff.x}, {order.dropoff.y})")
                        self._calculate_optimal_path(order.dropoff)

                    self._follow_current_path()
                    return

        # SEGUNDO: Si tiene orden actual pero no inventario, ir a recoger
        if self.current_order and not self.inventory:
            if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                picked_up = self.interact_at_position()
                if picked_up:

                    print(f"CPU {self.player_id}: Paquete recogido, calculando ruta a dropoff")
                    if self.inventory:
                        dropoff = self.inventory[0].dropoff
                        self._calculate_optimal_path(dropoff)
                    return
            else:
                if not self.current_target or \
                        self.current_target.x != self.current_order.pickup.x or \
                        self.current_target.y != self.current_order.pickup.y:
                    self._calculate_optimal_path(self.current_order.pickup)
                self._follow_current_path()
                return

        # TERCERO: Seguir camino si existe
        if self.current_path and self.path_index < len(self.current_path):
            self._follow_current_path()
            return

        # CUARTO: Si tiene orden pero sin camino, planear ruta
        if self.current_order:
            if self.action_state == "moving_to_pickup":
                if self.pos.x == self.current_order.pickup.x and self.pos.y == self.current_order.pickup.y:
                    picked_up = self.interact_at_position()
                    if picked_up:
                        # Calcular ruta al dropoff
                        if self.inventory:
                            dropoff = self.inventory[0].dropoff
                            self._calculate_optimal_path(dropoff)
                        return
                else:
                    self._calculate_optimal_path(self.current_order.pickup)

            elif self.action_state == "moving_to_dropoff" and self.inventory:
                if self.pos.x == self.inventory[0].dropoff.x and self.pos.y == self.inventory[0].dropoff.y:
                    delivered = self.interact_at_position()
                    if delivered:
                        self.current_path = []
                        self.path_index = 0
                        self.current_order = None

                        # Si todavía tiene paquetes, entregar el siguiente
                        if self.inventory:
                            next_dropoff = self.inventory[0].dropoff
                            self._calculate_optimal_path(next_dropoff)
                        return
                else:
                    self._calculate_optimal_path(self.inventory[0].dropoff)
            return

        # QUINTO: Replanificar secuencia óptima
        if self.replan_timer >= self.replan_interval or not self.current_order:
            self._plan_optimal_delivery_sequence()
            self.replan_timer = 0



    def _is_in_park(self) -> bool:
        """
        Verifica si el CPU está actualmente en un parque.

            True si está en un parque, False en caso contrario
        """
        if self.pos.y >= len(self.game.tiles) or self.pos.x >= len(self.game.tiles[self.pos.y]):
            return False

        tile_char = self.game.tiles[self.pos.y][self.pos.x]
        tile_info = self.game.legend.get(tile_char, {})

        # Obtener tipo y nombre del tile
        tile_type = tile_info.get('tipo', '').lower()
        tile_name = tile_info.get('name', '').lower()

        # Verificar si es parque
        is_park = (tile_type == 'park' or
                   'park' in tile_type or
                   'parque' in tile_name or
                   'parque' in tile_type)

        return is_park

    def _find_short_alternate_path(self, target: Position, max_depth: int = 8) -> Optional[List[Position]]:
        """
        Encuentra un camino alternativo corto usando BFS limitado.
        Útil cuando el camino directo está bloqueado pero hay rutas cercanas.
        """
        from collections import deque

        if not self._is_valid_move(self.pos):
            return None

        # Usar tuplas (x, y) en lugar de objetos Position para visited
        queue = deque([(self.pos, [self.pos])])
        visited = {(self.pos.x, self.pos.y)}

        directions = [
            (0, 1),  # Sur
            (0, -1),  # Norte
            (1, 0),  # Este
            (-1, 0)  # Oeste
        ]

        while queue:
            current_pos, path = queue.popleft()

            if len(path) > max_depth:
                continue

            if current_pos.x == target.x and current_pos.y == target.y:
                return path

            distance_to_target = abs(target.x - current_pos.x) + abs(target.y - current_pos.y)
            if distance_to_target <= 2 and len(path) > 1:
                return path

            for dx, dy in directions:
                next_pos = Position(current_pos.x + dx, current_pos.y + dy)
                next_tuple = (next_pos.x, next_pos.y)

                if next_tuple not in visited and self._is_valid_move(next_pos):
                    visited.add(next_tuple)
                    new_path = path + [next_pos]
                    queue.append((next_pos, new_path))

        return None

    def _should_rest_strategically(self) -> bool:
        """
        Determina si es estratégicamente beneficioso descansar ahora.
        Solo retorna True si stamina < 15 (crítico).
        """
        if self.stamina >= 15.0:
            return False

        nearest_park = self.find_nearest_park()
        if not nearest_park:
            return False

        distance_to_park = abs(self.pos.x - nearest_park.x) + abs(self.pos.y - nearest_park.y)

        if self.stamina < 10.0:
            return True

        if self.current_order:
            distance_to_pickup = abs(self.pos.x - self.current_order.pickup.x) + \
                                 abs(self.pos.y - self.current_order.pickup.y)

            # Si el parque está más cerca que el pickup y tiene poca stamina, ir al parque
            if distance_to_park < distance_to_pickup and self.stamina < 15.0:
                return True

        return self.stamina < 15.0

    def _estimate_stamina_needed_for_current_orders(self) -> float:
        """
        Estima cuánta stamina se necesita para completar las órdenes actuales.
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
        Calcula ruta óptima con A*.
        Mejor validación, logging y manejo de targets inválidos.
        """
        if not self.pathfinder:
            print(f"CPU {self.player_id}: Pathfinder no disponible, usando greedy")
            self.current_target = target
            self._greedy_move_towards_safe(target)
            return

        # DEBUG: Verificar posición actual
        if not self._is_valid_move(self.pos):
            print(f"CPU {self.player_id}: ERROR - Posición actual ({self.pos.x}, {self.pos.y}) no es válida!")
            return

        # VALIDACIÓN 1: Si el target no es walkable, encontrar posición cercana
        if not self._is_valid_move(target):
            print(f"CPU {self.player_id}: Target ({target.x}, {target.y}) no es caminable (edificio/bloqueado)")

            # Verificar qué tipo de tile es
            if target.y < len(self.game.tiles) and target.x < len(self.game.tiles[target.y]):
                tile_char = self.game.tiles[target.y][target.x]
                tile_info = self.game.legend.get(tile_char, {})
                tile_type = tile_info.get('tipo', 'unknown')
                print(f"CPU {self.player_id}: Tile en target es tipo '{tile_type}'")

            walkable_target = self.pathfinder.get_closest_walkable_position(target)

            if walkable_target:
                target = walkable_target
                print(f"CPU {self.player_id}: Usando target ajustado ({target.x}, {target.y})")
            else:
                print(f"CPU {self.player_id}: No se encontró posición caminable cercana")
                self.current_target = target
                self._greedy_move_towards_safe(target)
                return

        if self.pos.x == target.x and self.pos.y == target.y:
            self.current_path = []
            self.path_index = 0
            self.current_target = target
            return

        # Calcular camino con A*
        print(f"CPU {self.player_id}: Calculando A* desde ({self.pos.x},{self.pos.y}) hasta ({target.x},{target.y})")
        weather_penalty = self.game.weather_system.get_stamina_penalty()
        path = self.pathfinder.a_star(self.pos, target, weather_penalty)

        if path and len(path) > 1:
            # VALIDACIÓN 3: Verificar que el camino es válido
            valid_path = self._validate_path(path)

            if valid_path:
                self.current_path = path[1:]
                self.path_index = 0
                self.current_target = target
                self.stuck_counter = 0
                print(f"CPU {self.player_id}: Ruta A* exitosa ({len(self.current_path)} pasos)")
            else:
                print(f"CPU {self.player_id}: Camino A* inválido, intentando Dijkstra")
                path = self.pathfinder.dijkstra(self.pos, target, weather_penalty)

                if path and len(path) > 1 and self._validate_path(path):
                    self.current_path = path[1:]
                    self.path_index = 0
                    self.current_target = target
                    self.stuck_counter = 0
                    print(f"CPU {self.player_id}: Ruta Dijkstra exitosa ({len(self.current_path)} pasos)")
                else:
                    print(f"CPU {self.player_id}: Dijkstra también falló, usando greedy")
                    self.current_path = []
                    self.current_target = target
                    self._greedy_move_towards_safe(target)
        else:
            print(f"CPU {self.player_id}: A* no encontró camino, usando greedy")
            self.current_path = []
            self.current_target = target
            self._greedy_move_towards_safe(target)

    def _validate_path(self, path: List[Position]) -> bool:
        """
        Valida que un camino no tenga saltos ni posiciones inválidas.
        Validación más estricta de adyacencia y walkability.
        """
        if not path or len(path) == 0:
            return False

        for pos in path:
            if not self._is_valid_move(pos):
                print(f"CPU {self.player_id}: Camino contiene posición no transitable: ({pos.x}, {pos.y})")
                return False

        for i in range(len(path) - 1):
            current = path[i]
            next_pos = path[i + 1]

            dx = abs(next_pos.x - current.x)
            dy = abs(next_pos.y - current.y)

            is_orthogonal = (dx == 1 and dy == 0) or (dx == 0 and dy == 1)

            if not is_orthogonal:
                print(
                    f"CPU {self.player_id}: Camino tiene salto no ortogonal: ({current.x},{current.y}) -> ({next_pos.x},{next_pos.y})")
                return False

        return True

    def _follow_current_path(self):
        """
        Sigue el camino planificado con validación robusta.
        Mejor manejo cuando el camino se vuelve inválido y reintentos.
        """
        if not self.current_path or self.path_index >= len(self.current_path):
            self.current_path = []
            self.path_index = 0
            return

        next_pos = self.current_path[self.path_index]

        # Si ya está en la siguiente posición, avanzar
        if self.pos.x == next_pos.x and self.pos.y == next_pos.y:
            self.path_index += 1
            self.stuck_counter = 0
            return

        distance = abs(next_pos.x - self.pos.x) + abs(next_pos.y - self.pos.y)
        if distance > 1:
            print(f"CPU {self.player_id}: Camino con salto inválido detectado (distancia={distance}), replanificando")
            self.current_path = []
            self.path_index = 0
            self.stuck_counter = 0
            if self.current_target:
                self._calculate_optimal_path(self.current_target)
            return

        if not self._is_valid_move(next_pos):
            print(f"CPU {self.player_id}: Posición del camino bloqueada ({next_pos.x}, {next_pos.y}), replanificando")
            self.current_path = []
            self.path_index = 0
            self.stuck_counter = 0
            if self.current_target:
                self._calculate_optimal_path(self.current_target)
            return

        success = self.execute_move(next_pos, 0.016)

        if success:
            self.path_index += 1
            self.stuck_counter = 0

            if self.path_index >= len(self.current_path):
                self.current_path = []
                self.path_index = 0
        else:
            self.stuck_counter += 1
            print(f"CPU {self.player_id}: Movimiento falló (stuck_counter={self.stuck_counter})")

            # Si se atasca 3 veces, replanificar
            if self.stuck_counter >= 3:
                print(f"CPU {self.player_id}: Atascado {self.stuck_counter} veces, REPLANIFICANDO con A*")
                self.current_path = []
                self.path_index = 0
                self.stuck_counter = 0
                if self.current_target:
                    self._calculate_optimal_path(self.current_target)

    def _plan_rest_route(self):
        """
        Planifica ruta al parque con A*.
        Mejor manejo de errores y fallback.
        """
        nearest_park = self.find_nearest_park()

        if nearest_park:
            print(f"CPU {self.player_id}: Planificando ruta a parque en ({nearest_park.x}, {nearest_park.y})")

            # Verificar que el parque es una posición válida
            if self._is_valid_move(nearest_park):
                self._calculate_optimal_path(nearest_park)
            else:
                # Si el parque mismo no es transitable, buscar posición adyacente
                print(f"CPU {self.player_id}: Parque no transitable, buscando posición adyacente")
                if self.pathfinder:
                    walkable_park = self.pathfinder.get_closest_walkable_position(nearest_park)
                    if walkable_park:
                        print(
                            f"CPU {self.player_id}: Usando posición adyacente al parque: ({walkable_park.x}, {walkable_park.y})")
                        self._calculate_optimal_path(walkable_park)
                    else:
                        print(f"CPU {self.player_id}: No se encontró posición transitable cerca del parque")
                else:
                    print(f"CPU {self.player_id}: Pathfinder no disponible")
        else:
            print(f"CPU {self.player_id}: No hay parques disponibles en el mapa")

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
            optimized_sequence = self._plan_delivery_sequence(top_orders)
            if optimized_sequence:
                top_orders = optimized_sequence

        if top_orders:
            self.current_order = top_orders[0]
            self.orders_sequence = top_orders[1:]
            self.action_state = "moving_to_pickup"
            self._calculate_optimal_path(self.current_order.pickup)

    def _plan_delivery_sequence(self, orders: List[Order]) -> List[Order]:
        """
        Planifica la secuencia óptima de entregas usando TSP aproximado.
        Utiliza el algoritmo Nearest Neighbor para resolver una aproximación
        del problema del viajante (Traveling Salesman Problem).
            orders: Lista de órdenes a secuenciar
            Lista de órdenes ordenadas según la ruta óptima aproximada

        Algoritmo:
            Nearest Neighbor TSP - O(n²)
            - Comienza desde la posición actual
            - En cada paso, elige el pickup más cercano no visitado
            - Continúa hasta visitar todos los pickups
        """
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
        Considera si tendrá suficiente stamina para completarla.
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

    def _find_short_alternate_path(self, target: Position, max_depth: int = 8) -> Optional[List[Position]]:
        """
        Encuentra un camino alternativo corto usando BFS limitado.
        Útil cuando el camino directo está bloqueado pero hay rutas cercanas.
            target: Posición objetivo
            max_depth: Profundidad máxima de búsqueda (número de pasos)
            Lista de posiciones formando el camino, o None si no se encuentra
        """
        from collections import deque

        if not self._is_valid_move(self.pos):
            return None

        # Cola: (posición, camino hasta esa posición)
        queue = deque([(self.pos, [self.pos])])
        visited = {self.pos}

        directions = [
            Position(0, 1),  # Sur
            Position(0, -1),  # Norte
            Position(1, 0),  # Este
            Position(-1, 0)  # Oeste
        ]

        while queue:
            current_pos, path = queue.popleft()

            if len(path) > max_depth:
                continue

            if current_pos.x == target.x and current_pos.y == target.y:
                return path

            distance_to_target = abs(target.x - current_pos.x) + abs(target.y - current_pos.y)
            if distance_to_target <= 2:
                return path

            for direction in directions:
                next_pos = Position(current_pos.x + direction.x, current_pos.y + direction.y)

                if next_pos not in visited and self._is_valid_move(next_pos):
                    visited.add(next_pos)
                    new_path = path + [next_pos]
                    queue.append((next_pos, new_path))

        return None

    def _greedy_move_towards_safe(self, target: Position):
        """
        Movimiento greedy con mejor evitación de obstáculos.
        Usa BFS limitado para encontrar rutas alternativas cuando está bloqueado.
        """
        current_distance = abs(target.x - self.pos.x) + abs(target.y - self.pos.y)

        # Si ya está en el destino, no hacer nada
        if current_distance == 0:
            return

        moves = []
        directions = [
            Position(self.pos.x + 1, self.pos.y),  # Este
            Position(self.pos.x - 1, self.pos.y),  # Oeste
            Position(self.pos.x, self.pos.y + 1),  # Sur
            Position(self.pos.x, self.pos.y - 1)  # Norte
        ]

        for direction in directions:
            if not self._is_valid_move(direction):
                continue

            new_distance = abs(target.x - direction.x) + abs(target.y - direction.y)

            distance_improvement = current_distance - new_distance
            safety_bonus = self._calculate_safety_score(direction)

            # Score favorece movimientos que reducen distancia
            score = (distance_improvement * 10.0) + (safety_bonus * 0.3)

            moves.append((direction, score, new_distance))

        if not moves:
            print(f"CPU {self.player_id}: Sin movimientos válidos disponibles")
            self.stuck_counter += 1
            return

        moves.sort(key=lambda x: x[1], reverse=True)

        best_move, best_score, new_distance = moves[0]

        if new_distance < current_distance:
            success = self.execute_move(best_move, 0.016)
            if success:
                self.stuck_counter = 0
                return
            else:
                self.stuck_counter += 1
                # Si falla, intentar el segundo mejor
                if len(moves) > 1:
                    second_move, _, second_distance = moves[1]
                    if second_distance < current_distance:
                        if self.execute_move(second_move, 0.016):
                            self.stuck_counter = 0
                            return

        print(f"CPU {self.player_id}: Bloqueado directamente, buscando ruta alternativa con BFS")

        try:
            alternate_path = self._find_short_alternate_path(target)

            if alternate_path and len(alternate_path) > 1:
                next_step = alternate_path[1]  # [0] es la posición actual
                success = self.execute_move(next_step, 0.016)
                if success:
                    self.stuck_counter = 0
                    print(f"CPU {self.player_id}: Usando ruta alternativa BFS")
                    return
                else:
                    self.stuck_counter += 1
        except Exception as e:
            print(f"CPU {self.player_id}: Error en BFS alternativo: {e}")
            self.stuck_counter += 1

        print(f"CPU {self.player_id}: Último recurso - intentando cualquier movimiento válido")
        for move, _, _ in moves:
            if self.execute_move(move, 0.016):
                self.stuck_counter = 0
                return

        self.stuck_counter += 1
        print(f"CPU {self.player_id}: Completamente atascado (contador: {self.stuck_counter})")

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

    def _check_opportunistic_pickup(self) -> bool:
        """
        Verifica si hay paquetes disponibles en un rango de 1 casilla que puede recoger.
        Si los hay y tiene capacidad, los recoge oportunistamente.

        Returns:
            True si recogió un paquete, False si no
        """
        if not self.inventory:
            return False

        current_weight = self.get_current_weight()
        if current_weight >= self.max_weight:
            return False

        available_orders = self.get_available_orders()

        for order in available_orders:
            distance = abs(self.pos.x - order.pickup.x) + abs(self.pos.y - order.pickup.y)

            if distance <= 1 and self.has_capacity_for(order):
                score = self._calculate_order_score(order)

                if score > 0:
                    print(f"CPU {self.player_id}: ¡Oportunidad! Paquete {order.id} a {distance} casilla(s)")

                    if distance == 0:
                        # Guardar el estado actual
                        previous_order = self.current_order
                        previous_target = self.current_target

                        self.current_order = order
                        picked_up = self.interact_at_position()

                        if picked_up:
                            print(f"CPU {self.player_id}: Recogió paquete oportunista {order.id}")
                            # Restaurar la orden anterior como objetivo principal
                            self.current_order = previous_order
                            self.current_target = previous_target
                            return True
                        else:
                            # Si falló, restaurar
                            self.current_order = previous_order
                            self.current_target = previous_target
                            return False

                    # Si está a 1 casilla, hacer un desvío rápido
                    elif distance == 1:
                        print(f"CPU {self.player_id}: Haciendo desvío de 1 casilla para recoger {order.id}")

                        if not hasattr(self, '_saved_delivery_target'):
                            self._saved_delivery_target = None

                        if self.inventory and len(self.inventory) > 0:
                            self._saved_delivery_target = self.inventory[0].dropoff

                        self.current_order = order
                        self._calculate_optimal_path(order.pickup)
                        self.action_state = "opportunistic_pickup"
                        return True

        return False

    def _handle_opportunistic_state(self) -> bool:
        """
        Maneja el estado especial de recolección oportunista.

            True si está en modo oportunista y debe continuar, False si terminó
        """
        if not hasattr(self, 'action_state') or self.action_state != "opportunistic_pickup":
            return False

        if self.current_order and \
                self.pos.x == self.current_order.pickup.x and \
                self.pos.y == self.current_order.pickup.y:

            picked_up = self.interact_at_position()

            if picked_up:
                print(f"CPU {self.player_id}: Recogió paquete oportunista {self.current_order.id}")

                # Restaurar el objetivo de entrega original
                self.current_order = None
                self.action_state = "moving_to_dropoff"

                # Recalcular ruta al dropoff original
                if hasattr(self, '_saved_delivery_target') and self._saved_delivery_target:
                    print(f"CPU {self.player_id}: Regresando a entrega original")
                    self._calculate_optimal_path(self._saved_delivery_target)
                    self._saved_delivery_target = None
                elif self.inventory:
                    # Ir al dropoff del primer paquete en inventario
                    self._calculate_optimal_path(self.inventory[0].dropoff)

                return True
            else:
                # Si falló la recolección, volver al estado normal
                self.action_state = "moving_to_dropoff"
                if hasattr(self, '_saved_delivery_target') and self._saved_delivery_target:
                    self._calculate_optimal_path(self._saved_delivery_target)
                    self._saved_delivery_target = None
                return True
        else:
            # Seguir el camino al pickup oportunista
            self._follow_current_path()
            return True




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