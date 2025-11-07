"""
Estructuras de datos para grafos y algoritmos de pathfinding
Utilizados para la IA del CPU Player (nivel difícil)
"""

import heapq
from typing import List, Dict, Tuple, Optional, Set
from models.order import Position


class Node:
    """Nodo para algoritmos de búsqueda con información de pathfinding."""

    def __init__(self, position: Position, g_cost: float = 0, h_cost: float = 0, parent=None):
        self.position = position
        self.g_cost = g_cost  # Costo desde el inicio
        self.h_cost = h_cost  # Heurística al objetivo
        self.f_cost = g_cost + h_cost  # Costo total
        self.parent = parent

    def __lt__(self, other):
        """Comparación para heap queue (prioridad)."""
        return self.f_cost < other.f_cost

    def __eq__(self, other):
        """Igualdad basada en posición."""
        if not isinstance(other, Node):
            return False
        return self.position.x == other.position.x and self.position.y == other.position.y

    def __hash__(self):
        """Hash para usar en sets y dicts."""
        return hash((self.position.x, self.position.y))


class WeightedGraph:
    """Grafo ponderado para representar la ciudad."""

    def __init__(self, width: int, height: int, tiles: List[List[str]], legend: Dict):
        self.width = width
        self.height = height
        self.tiles = tiles
        self.legend = legend
        self.adjacency_list = {}
        self._build_graph()

    def _build_graph(self):
        """Construye el grafo basándose en el mapa de tiles."""
        for y in range(self.height):
            for x in range(self.width):
                pos = Position(x, y)
                if self.is_walkable(pos):
                    self.adjacency_list[pos] = self._get_neighbors(pos)

    def is_walkable(self, pos: Position) -> bool:
        """Verifica si una posición es transitable (no es edificio)."""
        if not self.is_valid_position(pos):
            return False

        tile_char = self.tiles[pos.y][pos.x]
        tile_type = self.legend.get(tile_char, {}).get('tipo', 'street')
        return tile_type != 'building'

    def is_valid_position(self, pos: Position) -> bool:
        """Verifica si una posición está dentro de los límites."""
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def _get_neighbors(self, pos: Position) -> List[Position]:
        """Obtiene vecinos transitables de una posición."""
        neighbors = []
        directions = [
            Position(0, -1),  # Norte
            Position(0, 1),   # Sur
            Position(-1, 0),  # Oeste
            Position(1, 0)    # Este
        ]

        for direction in directions:
            new_pos = Position(pos.x + direction.x, pos.y + direction.y)
            if self.is_walkable(new_pos):
                neighbors.append(new_pos)

        return neighbors

    def get_neighbors(self, pos: Position) -> List[Position]:
        """Obtiene vecinos de una posición desde el grafo construido."""
        return self.adjacency_list.get(pos, [])

    def get_tile_cost(self, pos: Position, weather_penalty: float = 0.0) -> float:
        """Calcula el costo de moverse a un tile considerando tipo y clima."""
        if not self.is_valid_position(pos):
            return float('inf')

        tile_char = self.tiles[pos.y][pos.x]
        tile_info = self.legend.get(tile_char, {})
        tile_type = tile_info.get('tipo', 'street')
        surface = tile_info.get('superficie', 'asphalt')

        # Costo base por superficie
        base_costs = {
            'asphalt': 1.0,
            'concrete': 1.1,
            'dirt': 1.5,
            'grass': 2.0,
            'cobblestone': 1.3
        }
        base_cost = base_costs.get(surface, 1.0)

        # Parques son preferibles para descanso
        if tile_type == 'park':
            base_cost *= 0.8  # Reducir costo en parques

        # Aplicar penalización del clima
        return base_cost * (1.0 + weather_penalty)


class PathFinder:
    """Implementa algoritmos de búsqueda de caminos."""

    def __init__(self, graph: WeightedGraph):
        self.graph = graph

    @staticmethod
    def manhattan_distance(pos1: Position, pos2: Position) -> float:
        """Calcula distancia Manhattan entre dos posiciones."""
        return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)

    @staticmethod
    def euclidean_distance(pos1: Position, pos2: Position) -> float:
        """Calcula distancia euclidiana entre dos posiciones."""
        return ((pos1.x - pos2.x) ** 2 + (pos1.y - pos2.y) ** 2) ** 0.5

    def a_star(self, start: Position, goal: Position, weather_penalty: float = 0.0) -> Optional[List[Position]]:
        """
        Algoritmo A* para encontrar el camino más corto.

        Args:
            start: Posición inicial
            goal: Posición objetivo
            weather_penalty: Penalización adicional por clima (0.0 - 1.0)

        Returns:
            Lista de posiciones que forman el camino, o None si no existe camino
        """
        if not self.graph.is_walkable(start) or not self.graph.is_walkable(goal):
            return None

        # Conjuntos de nodos abiertos y cerrados
        open_set = []
        closed_set = set()

        # Nodo inicial
        start_node = Node(start, g_cost=0, h_cost=self.manhattan_distance(start, goal))
        heapq.heappush(open_set, start_node)

        # Diccionario para tracking del mejor g_cost a cada posición
        g_costs = {start: 0}

        while open_set:
            current_node = heapq.heappop(open_set)

            # Si llegamos al objetivo, reconstruir camino
            if current_node.position.x == goal.x and current_node.position.y == goal.y:
                return self._reconstruct_path(current_node)

            # Marcar como visitado
            closed_set.add(current_node.position)

            # Explorar vecinos
            for neighbor_pos in self.graph.get_neighbors(current_node.position):
                if neighbor_pos in closed_set:
                    continue

                # Calcular costo del movimiento
                move_cost = self.graph.get_tile_cost(neighbor_pos, weather_penalty)
                tentative_g = current_node.g_cost + move_cost

                # Si encontramos un mejor camino o es un nodo nuevo
                if neighbor_pos not in g_costs or tentative_g < g_costs[neighbor_pos]:
                    g_costs[neighbor_pos] = tentative_g
                    h_cost = self.manhattan_distance(neighbor_pos, goal)
                    neighbor_node = Node(neighbor_pos, tentative_g, h_cost, current_node)
                    heapq.heappush(open_set, neighbor_node)

        # No se encontró camino
        return None

    def dijkstra(self, start: Position, goal: Position, weather_penalty: float = 0.0) -> Optional[List[Position]]:
        """
        Algoritmo de Dijkstra para encontrar el camino más corto.
        Similar a A* pero sin heurística (h_cost = 0).

        Args:
            start: Posición inicial
            goal: Posición objetivo
            weather_penalty: Penalización adicional por clima (0.0 - 1.0)

        Returns:
            Lista de posiciones que forman el camino, o None si no existe camino
        """
        if not self.graph.is_walkable(start) or not self.graph.is_walkable(goal):
            return None

        # Priority queue: (costo, posición, nodo)
        open_set = []
        start_node = Node(start, g_cost=0, h_cost=0)
        heapq.heappush(open_set, start_node)

        # Diccionarios de tracking
        distances = {start: 0}
        visited = set()

        while open_set:
            current_node = heapq.heappop(open_set)
            current_pos = current_node.position

            if current_pos in visited:
                continue

            visited.add(current_pos)

            # Si llegamos al objetivo
            if current_pos.x == goal.x and current_pos.y == goal.y:
                return self._reconstruct_path(current_node)

            # Explorar vecinos
            for neighbor_pos in self.graph.get_neighbors(current_pos):
                if neighbor_pos in visited:
                    continue

                move_cost = self.graph.get_tile_cost(neighbor_pos, weather_penalty)
                new_distance = current_node.g_cost + move_cost

                if neighbor_pos not in distances or new_distance < distances[neighbor_pos]:
                    distances[neighbor_pos] = new_distance
                    neighbor_node = Node(neighbor_pos, new_distance, 0, current_node)
                    heapq.heappush(open_set, neighbor_node)

        return None

    def bfs(self, start: Position, goal: Position) -> Optional[List[Position]]:
        """
        Breadth-First Search para encontrar camino (sin pesos).
        Útil cuando todos los movimientos tienen el mismo costo.

        Args:
            start: Posición inicial
            goal: Posición objetivo

        Returns:
            Lista de posiciones que forman el camino, o None si no existe camino
        """
        if not self.graph.is_walkable(start) or not self.graph.is_walkable(goal):
            return None

        from collections import deque

        queue = deque([Node(start)])
        visited = {start}

        while queue:
            current_node = queue.popleft()

            # Si llegamos al objetivo
            if current_node.position.x == goal.x and current_node.position.y == goal.y:
                return self._reconstruct_path(current_node)

            # Explorar vecinos
            for neighbor_pos in self.graph.get_neighbors(current_node.position):
                if neighbor_pos not in visited:
                    visited.add(neighbor_pos)
                    neighbor_node = Node(neighbor_pos, parent=current_node)
                    queue.append(neighbor_node)

        return None

    def _reconstruct_path(self, node: Node) -> List[Position]:
        """Reconstruye el camino desde el nodo objetivo hasta el inicio."""
        path = []
        current = node

        while current is not None:
            path.append(current.position)
            current = current.parent

        path.reverse()
        return path

    def get_closest_walkable_position(self, target: Position) -> Optional[Position]:
        """
        Encuentra la posición transitable más cercana a un objetivo.
        Útil cuando el objetivo está en un edificio.
        """
        if self.graph.is_walkable(target):
            return target

        # BFS para encontrar el tile transitable más cercano
        from collections import deque

        queue = deque([target])
        visited = {target}

        while queue:
            current = queue.popleft()

            # Revisar vecinos (incluyendo diagonales)
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue

                    neighbor = Position(current.x + dx, current.y + dy)

                    if neighbor not in visited and self.graph.is_valid_position(neighbor):
                        visited.add(neighbor)

                        if self.graph.is_walkable(neighbor):
                            return neighbor

                        queue.append(neighbor)

        return None


class TSPSolver:
    """
    Resolvedor aproximado del problema del vendedor viajero (TSP).
    Útil para optimizar secuencias de entregas.
    """

    def __init__(self, pathfinder: PathFinder):
        self.pathfinder = pathfinder

    def nearest_neighbor(self, start: Position, targets: List[Position]) -> List[Position]:
        """
        Algoritmo del vecino más cercano para TSP.
        Heurística greedy simple pero efectiva.

        Args:
            start: Posición inicial
            targets: Lista de posiciones a visitar

        Returns:
            Lista ordenada de posiciones en el orden óptimo aproximado
        """
        if not targets:
            return []

        unvisited = set(range(len(targets)))
        route = []
        current_pos = start

        while unvisited:
            # Encontrar el objetivo no visitado más cercano
            closest_idx = None
            closest_dist = float('inf')

            for idx in unvisited:
                target = targets[idx]
                dist = PathFinder.manhattan_distance(current_pos, target)

                if dist < closest_dist:
                    closest_dist = dist
                    closest_idx = idx

            # Agregar al route y marcar como visitado
            if closest_idx is not None:
                route.append(targets[closest_idx])
                current_pos = targets[closest_idx]
                unvisited.remove(closest_idx)

        return route

    def two_opt(self, route: List[Position], max_iterations: int = 100) -> List[Position]:
        """
        Algoritmo 2-opt para mejorar una ruta TSP.
        Intenta intercambiar segmentos de la ruta para reducir la distancia total.

        Args:
            route: Ruta inicial
            max_iterations: Máximo número de iteraciones

        Returns:
            Ruta mejorada
        """
        if len(route) < 4:
            return route

        improved = True
        best_route = route[:]
        iterations = 0

        while improved and iterations < max_iterations:
            improved = False
            iterations += 1

            for i in range(1, len(best_route) - 2):
                for j in range(i + 1, len(best_route)):
                    if j - i == 1:
                        continue

                    # Calcular distancia de la ruta actual
                    current_dist = (
                        PathFinder.manhattan_distance(best_route[i - 1], best_route[i]) +
                        PathFinder.manhattan_distance(best_route[j - 1], best_route[j])
                    )

                    # Calcular distancia si invertimos el segmento
                    new_dist = (
                        PathFinder.manhattan_distance(best_route[i - 1], best_route[j - 1]) +
                        PathFinder.manhattan_distance(best_route[i], best_route[j])
                    )

                    # Si mejora, aplicar el intercambio
                    if new_dist < current_dist:
                        best_route[i:j] = reversed(best_route[i:j])
                        improved = True

        return best_route
