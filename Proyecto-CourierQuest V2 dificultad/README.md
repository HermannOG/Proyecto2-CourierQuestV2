# Courier Quest - Proyecto EIF-207

## Descripción General

Courier Quest es un videojuego desarrollado en Python usando Pygame que simula a un repartidor en bicicleta que debe completar pedidos en una ciudad, gestionando tiempo, clima, resistencia y reputación. El juego permite experimentar la logística y toma de decisiones en tiempo real, incorporando estructuras de datos y algoritmos fundamentales.

## Características Principales

- **Mundo dinámico:** Ciudad representada como cuadrícula con calles, edificios y parques.
- **Sistema de pedidos:** Gestión de pedidos con prioridades y plazos.
- **Clima dinámico:** Sistema de clima que cambia usando cadenas de Markov.
- **Mecánicas de jugador:** Resistencia, reputación, velocidad variable.
- **Integración API:** Conecta con API externa con fallback a archivos locales.
- **Persistencia:** Guardado/carga de partidas y tabla de puntajes.
- **Sistema de deshacer:** Historial de estados para revertir acciones.

## Estructuras de Datos Utilizadas

### 1. Cola de Prioridad (PriorityQueue)
**Uso:** Gestión de pedidos disponibles ordenados por prioridad  
**Implementación:** Lista ordenada con inserción por prioridad  
**Complejidad:**  
- Inserción: O(n)
- Eliminación: O(1)
- Búsqueda: O(1) (peek del elemento prioritario)

```python
class PriorityQueue:
    def enqueue(self, item: Order):  # O(n)
    def dequeue(self) -> Optional[Order]:  # O(1)
    def peek(self) -> Optional[Order]:  # O(1)
```

### 2. Deque (Collections.deque)
**Uso:** Inventario del jugador para navegación bidireccional  
**Implementación:** Cola doblemente enlazada de Python  
**Complejidad:**  
- Inserción/eliminación en extremos: O(1)
- Acceso aleatorio/búsqueda: O(n)

```python
self.inventory = deque()  # Inventario del jugador
```

### 3. Pila (Stack) - GameHistory
**Uso:** Sistema de deshacer movimientos del jugador  
**Implementación:** Lista tipo LIFO  
**Complejidad:**  
- Push: O(1)
- Pop: O(1)
- Tamaño limitado para gestión de memoria

```python
class GameHistory:
    def push(self, state: GameState):  # O(1)
    def pop(self) -> Optional[GameState]:  # O(1)
```

### 4. Diccionarios (Dict)
**Uso:**  
- Configuración del mapa y leyenda de tiles
- Matriz de transición de Markov para clima
- Datos de configuración del juego  
**Complejidad:** O(1) promedio para acceso y modificación

### 5. Listas (List)
**Uso:**  
- Representación de la cuadrícula del mapa
- Almacenamiento de pedidos completados
- Historial de estados del juego  
**Complejidad:** O(1) para acceso por índice, O(n) para búsqueda

## Algoritmos Implementados

### 1. Cadenas de Markov para Clima
**Complejidad:** O(k), donde k es el número de estados climáticos  
**Descripción:** Transición probabilística entre estados usando matriz de transición.

### 2. Pathfinding Implícito
**Complejidad:** O(1) por movimiento  
**Descripción:** Movimiento basado en reglas de adyacencia en cuadrícula.

### 3. Ordenamiento de Inventario
**Complejidad:** O(n log n) usando sort() de Python  
**Criterios:** Prioridad y deadline de pedidos.

### 4. Gestión de Caché
**Complejidad:** O(1) para acceso, O(n) para escritura  
**Descripción:** Sistema de caché con fallback automático.

## Instalación y Ejecución

### Requisitos
- Python 3.8+
- Pygame 2.0+
- Requests library

### Instalación
```bash
pip install pygame requests
```

### Ejecución
```bash
python courier_quest.py
```

## Controles del Juego

| Tecla          | Función                    |
|----------------|---------------------------|
| WASD / Flechas | Mover jugador             |
| E              | Interactuar (recoger/entregar) |
| I              | Mostrar/ocultar inventario |
| O              | Mostrar/ocultar pedidos    |
| SPACE          | Pausar/reanudar            |
| F5             | Guardar partida            |
| F9             | Cargar partida             |
| Ctrl+Z         | Deshacer movimiento        |
| ESC            | Salir (en game over)       |

### Inventario (Tecla I)
- **1**: Ordenar por prioridad
- **2**: Ordenar por deadline
- **ENTER**: Entregar pedido seleccionado (en destino)

### Pedidos (Tecla O)
- **ENTER**: Aceptar pedido seleccionado
- **Flechas**: Navegar lista

## Mecánicas del Juego

### Sistema de Resistencia
- **Rango:** 0-100
- **Estados:** Normal (>30), Cansado (10-30), Exhausto (≤0)
- **Recuperación:** 5 puntos/segundo en reposo
- **Consumo:**  
  - Movimiento base: -0.5 por celda
  - Peso extra: -0.2 por kg sobre 3kg
  - Clima adverso: variable según condición

### Sistema de Reputación
- **Rango:** 0-100 (inicio: 70)
- **Efectos:**  
  - ≥90: Bonus +5% en pagos
  - <20: Derrota inmediata
- **Cambios:**  
  - Entrega temprana: +5
  - Entrega puntual: +3
  - Tardanza leve: -2 a -10
  - Cancelación: -4

### Sistema de Clima
Condiciones soportadas con multiplicadores:
- **clear**: ×1.00
- **clouds**: ×0.98
- **rain_light**: ×0.90
- **rain**: ×0.85
- **storm**: ×0.75
- **fog**: ×0.88
- **wind**: ×0.92
- **heat**: ×0.90
- **cold**: ×0.92

## Integración con API

### Endpoints Utilizados
- `GET /city/map` → Configuración del mapa
- `GET /city/jobs` → Lista de pedidos disponibles  
- `GET /city/weather` → Datos de clima por ráfagas

### Sistema de Caché
1. **Primer intento:** Conexión a API externa
2. **Segundo intento:** Archivo en caché local (`api_cache/`)
3. **Fallback final:** Archivos por defecto (`data/`)

### Modo Offline
El juego funciona completamente sin conexión usando:
- Datos pre-generados en `/data/`
- Sistema de caché inteligente
- Generación procedural de pedidos

## Algoritmos de Ordenamiento

### Pedidos por Prioridad
```python
def enqueue(self, item: Order):
    for i, existing in enumerate(self.items):
        if item.priority > existing.priority:
            self.items.insert(i, item)  # O(n)
            return
```

### Inventario por Criterios
```python
inventory_list.sort(key=lambda x: x.priority, reverse=True)  # O(n log n)
inventory_list.sort(key=lambda x: x.deadline)  # O(n log n)
```

### Tabla de Puntajes
```python
scores.sort(key=lambda x: x['score'], reverse=True)  # O(n log n)
```

## Complejidad Algorítmica

| Operación                   | Complejidad | Estructura      |
|-----------------------------|-------------|-----------------|
| Agregar pedido disponible   | O(n)        | PriorityQueue   |
| Obtener mejor pedido        | O(1)        | PriorityQueue   |
| Agregar a inventario        | O(1)        | Deque           |
| Navegar inventario          | O(1)        | Deque           |
| Guardar estado (deshacer)   | O(k)        | Stack           |
| Deshacer movimiento         | O(1)        | Stack           |
| Ordenar inventario          | O(n log n)  | List.sort()     |
| Actualizar clima            | O(k)        | Markov Chain    |
| Verificar colisiones        | O(1)        | Grid lookup     |
| Guardar/cargar partida      | O(n)        | Pickle          |

Donde:  
- n = número de pedidos  
- k = número de estados climáticos (~9)

### Eficiencia de Memoria
- **Historial de estados:** Limitado a 50 estados (bounded stack)
- **Caché de API:** Archivos JSON compactos
- **Inventario:** Máximo 10kg de capacidad (naturalmente limitado)

## Formato de Archivos

### Guardado Binario (`saves/slot1.sav`)
- **Formato:** Pickle
- **Contenido:** Estado completo del juego
- **Ventaja:** Rápido y compacto

### Puntajes JSON (`data/puntajes.json`)
```json
[
  {
    "score": 3250,
    "money": 3100,
    "reputation": 85,
    "date": "2025-09-28T10:30:00",
    "victory": true
  }
]
```

### Configuración de Ciudad (`data/ciudad.json`)
```json
{
  "version": "1.0",
  "width": 20,
  "height": 15,
  "tiles": [["C","C","B"],["P","C","C"]],
  "legend": {
    "C": {"name":"calle","surface_weight":1.00},
    "B": {"name":"edificio","blocked":true},
    "P": {"name":"parque","surface_weight":0.95}
  },
  "goal": 3000
}
```

## Instalación Rápida

1. **Clonar repositorio:**
   ```bash
   git clone https://github.com/HermannOG/CourierQuest.git
   cd CourierQuest
   ```
2. **Instalar dependencias:**
   ```bash
   pip install pygame requests
   ```
3. **Ejecutar juego:**
   ```bash
   python courier_quest.py
   ```

## Estrategias de Juego

### Para Principiantes
1. Gestiona tu resistencia: evita moverte con resistencia baja.
2. Prioriza pedidos de alta prioridad y pago.
3. Planifica rutas eficientes.
4. Ajusta tu estrategia según el clima.

### Para Expertos
1. Optimiza rutas agrupando entregas por zona.
2. Balancea ganancia y reputación.
3. Usa el deshacer estratégicamente.
4. Busca entregas tempranas para bonificaciones.

## Extensiones Futuras

- Multijugador (competencia entre repartidores)
- Power-ups (mejoras temporales)
- Eventos especiales (festivos, promociones)
- Personalización (vehículos y equipamiento)
- Tutorial interactivo para nuevos jugadores

## Créditos

Desarrollado como proyecto académico para EIF-207 Estructuras de Datos, II Ciclo 2025.

**Tecnologías utilizadas:**
- Python 3.8+
- Pygame 2.0+
- Requests
- JSON para persistencia
- Pickle para guardado binario

## Notas de Desarrollo

### Decisiones de Diseño

1. Pygame sobre Arcade: mayor control sobre renderizado y eventos.
2. Pickle para guardado: serialización eficiente.
3. Deque para inventario: navegación bidireccional eficiente.
4. Sistema de caché robusto: garantiza funcionamiento offline.

### Optimizaciones Implementadas

1. Bounded Stack: historial limitado para evitar uso excesivo de memoria.
2. Lazy Loading: datos cargados solo cuando son necesarios.
3. Caching Strategy: múltiples niveles de fallback.
4. Efficient Rendering: solo se redibujan elementos que cambian.

### Manejo de Errores

- Fallos de API: fallback automático a caché/archivos locales.
- Corrupción de archivos: regeneración automática.
- Guardados inválidos: validación antes de cargar.
- Timeouts de red: configuración de tiempo de espera.

## Testing y Validación

### Casos de Prueba Sugeridos

1. **Conectividad:**
   - Probar con/sin internet
   - Validar fallback a archivos locales
   - Verificar creación de caché

2. **Mecánicas de Juego:**
   - Agotamiento de resistencia
   - Pérdida de reputación por tardanza
   - Victoria por alcanzar meta

3. **Sistema de Archivos:**
   - Guardado/carga de partidas
   - Persistencia de puntajes
   - Corrupción de archivos

4. **Rendimiento:**
   - FPS estable en 60
   - Uso de memoria controlado
   - Tiempo de carga aceptable

## Colaboración

¿Quieres contribuir?  
- Crea un fork y propone mejoras mediante pull requests.
- Usa issues para reportar bugs o sugerir nuevas funcionalidades.
- Sigue la guía de estilo de código incluida en el repositorio.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo LICENSE para más detalles.

---

*Para más información sobre la implementación, consulta los comentarios en el código fuente.*

