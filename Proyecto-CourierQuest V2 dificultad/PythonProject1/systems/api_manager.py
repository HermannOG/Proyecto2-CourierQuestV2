# systems/api_manager.py
import os
import json
import requests
import random
import pygame
from typing import Any, Optional, List
from models.order import Order, Position
from config.constants import TILE_SIZE


class TigerAPIManager:
    def __init__(self, base_url="https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io"):
        self.base_url = base_url
        self.cache_dir = "api_cache"
        self.data_dir = "data"
        self._ensure_directories()
        self.tile_images = {}
        self._load_tile_images()

    def _load_tile_images(self):
        try:
            park_image = pygame.image.load("pixilart-drawing.png")
            self.tile_images["P"] = pygame.transform.scale(park_image, (TILE_SIZE, TILE_SIZE))
            print(" Imagen de parque cargada correctamente desde pixilart-drawing.png")
        except FileNotFoundError as e:
            print(f" No se pudo cargar imagen: {e}")
            self._create_fallback_images()
        except Exception as e:
            print(f" Error cargando imágenes: {e}")
            self._create_fallback_images()

    def _create_fallback_images(self):
        park_surface = pygame.Surface((TILE_SIZE, TILE_SIZE))
        park_surface.fill((0, 200, 0))

        tree_color = (0, 100, 0)
        for i in range(3):
            for j in range(3):
                if (i + j) % 2 == 0:
                    tree_rect = pygame.Rect(
                        i * (TILE_SIZE // 3) + 2,
                        j * (TILE_SIZE // 3) + 2,
                        TILE_SIZE // 3 - 4,
                        TILE_SIZE // 3 - 4
                    )
                    pygame.draw.ellipse(park_surface, tree_color, tree_rect)
        self.tile_images["P"] = park_surface
        print(" Imagen de respaldo para parque creada")

    def _ensure_directories(self):
        for directory in [self.cache_dir, self.data_dir]:
            os.makedirs(directory, exist_ok=True)

    def make_request(self, endpoint, timeout=30):
        try:
            resp = requests.get(self.base_url + endpoint, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f" Error {resp.status_code} en {endpoint}")
                return None
        except Exception as e:
            print(f" Error de conexión en {endpoint}: {e}")
            return None

    def get_city_map(self) -> dict:
        print(" Obteniendo mapa de TigerCity desde API...")
        map_data = self.make_request("/city/map")

        if map_data and 'data' in map_data:
            api_data = map_data['data']
            game_map = {
                'width': api_data['width'],
                'height': api_data['height'],
                'tiles': api_data['tiles'],
                'legend': self._convert_legend(api_data['legend']),
                'goal': 3000,
                'city_name': api_data.get('city_name', 'TigerCity'),
                'max_time': api_data.get('max_time', 600),
                'version': api_data.get('version', '1.0')
            }
            self._save_to_cache("map.json", game_map)
            print(f" Mapa cargado: {game_map['width']}x{game_map['height']} - {game_map['city_name']}")
            return game_map
        else:
            print(" No se pudo obtener el mapa de la API, usando datos locales...")
            return self._get_fallback_map()

    def get_city_jobs(self) -> list:
        print(" Obteniendo trabajos de TigerCity desde API...")
        jobs_data = self.make_request("/city/jobs")

        if jobs_data:
            orders = self._convert_jobs_to_orders(jobs_data)
            if len(orders) < 25:
                print(f"️ Solo {len(orders)} pedidos de API, generando adicionales...")
                additional_orders = self._generate_additional_orders(25 - len(orders))
                orders.extend(additional_orders)
            self._save_to_cache("jobs.json", orders)
            print(f" {len(orders)} pedidos cargados")
            return orders
        else:
            print("️ No se pudieron obtener los trabajos de la API...")
            return self._get_fallback_orders()

    def _generate_additional_orders(self, count: int) -> list:
        additional_orders = []
        for i in range(count):
            pickup_x = random.randint(1, 28)
            pickup_y = random.randint(1, 23)
            dropoff_x = random.randint(1, 28)
            dropoff_y = random.randint(1, 23)
            attempts = 0
            while abs(pickup_x - dropoff_x) + abs(pickup_y - dropoff_y) < 4 and attempts < 10:
                dropoff_x = random.randint(1, 28)
                dropoff_y = random.randint(1, 23)
                attempts += 1
            distance = abs(pickup_x - dropoff_x) + abs(pickup_y - dropoff_y)
            duration = max(1.5, min(4.5, distance * 0.25 + random.uniform(1.0, 2.0)))
            release_time = random.randint(0, 180)
            order = Order(
                id=f"GEN_{i + 100:03d}",
                pickup=Position(pickup_x, pickup_y),
                dropoff=Position(dropoff_x, dropoff_y),
                payout=random.randint(120, 280),
                duration_minutes=duration,
                weight=random.randint(1, 4),
                priority=random.choices([0, 1, 2], weights=[50, 35, 15])[0],
                release_time=release_time
            )
            additional_orders.append(order)
        return additional_orders

    def _convert_legend(self, api_legend: dict) -> dict:
        game_legend = {}
        for tile_type, tile_info in api_legend.items():
            game_tile = {
                'name': tile_info['name'],
                'surface_weight': tile_info.get('surface_weight', 1.0)
            }
            if tile_info.get('blocked', False):
                game_tile['blocked'] = True
            if tile_info['name'].lower() == 'park':
                game_tile['rest_bonus'] = 20.0
            game_legend[tile_type] = game_tile
        return game_legend

    def _convert_jobs_to_orders(self, jobs_data: dict) -> list:
        orders = []
        jobs_list = None

        try:
            if isinstance(jobs_data, dict):
                if 'data' in jobs_data and isinstance(jobs_data['data'], dict) and 'jobs' in jobs_data['data']:
                    jobs_list = jobs_data['data']['jobs']
                elif 'jobs' in jobs_data:
                    jobs_list = jobs_data['jobs']
                elif 'data' in jobs_data and isinstance(jobs_data['data'], list):
                    jobs_list = jobs_data['data']
            elif isinstance(jobs_data, list):
                jobs_list = jobs_data

            if not jobs_list or not isinstance(jobs_list, list):
                print(" Estructura de datos inesperada")
                return self._get_fallback_orders()

            for i, job in enumerate(jobs_list):
                try:
                    if isinstance(job, str):
                        order_id = f"STR_{i:03d}"
                        payout = random.randint(100, 200)
                    elif isinstance(job, dict):
                        order_id = job.get('id', f"API_{i:03d}")
                        payout = job.get('salary', job.get('payout', random.randint(100, 200)))
                    else:
                        continue

                    if isinstance(payout, str):
                        try:
                            payout = int(float(payout.replace('$', '').replace(',', '')))
                        except:
                            payout = random.randint(100, 200)

                    pickup_x = random.randint(1, 28)
                    pickup_y = random.randint(1, 23)
                    dropoff_x = random.randint(1, 28)
                    dropoff_y = random.randint(1, 23)

                    api_priority = random.randint(0, 2)

                    order = Order(
                        id=str(order_id),
                        pickup=Position(pickup_x, pickup_y),
                        dropoff=Position(dropoff_x, dropoff_y),
                        payout=int(payout),
                        duration_minutes=random.uniform(0.3, 0.8),
                        weight=random.randint(1, 3),
                        priority=api_priority,
                        release_time=random.randint(0, 180)
                    )
                    orders.append(order)
                except Exception as e:
                    print(f"⚠️ Error procesando trabajo {i}: {e}")
                    continue

            return orders if orders else self._get_fallback_orders()
        except Exception as e:
            print(f" Error general: {e}")
            return self._get_fallback_orders()

    def _save_to_cache(self, filename: str, data: Any):
        try:
            cache_path = os.path.join(self.cache_dir, filename)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            print(f"️ Error guardando caché: {e}")

    def _get_fallback_map(self) -> dict:
        return {
            "width": 30,
            "height": 25,
            "tiles": [["C"] * 30 for _ in range(25)],
            "legend": {
                "C": {"name": "calle", "surface_weight": 1.00},
                "B": {"name": "edificio", "blocked": True},
                "P": {"name": "parque", "surface_weight": 0.95, "rest_bonus": 15.0}
            },
            "goal": 3000,
            "city_name": "TigerCity",
            "max_time": 600,
            "version": "1.0"
        }

    def _get_fallback_orders(self) -> list:
        orders = []
        for i in range(35):
            orders.append(Order(
                id=f"FALLBACK_{i:03d}",
                pickup=Position(random.randint(1, 28), random.randint(1, 23)),
                dropoff=Position(random.randint(1, 28), random.randint(1, 23)),
                payout=random.randint(150, 400),
                duration_minutes=random.uniform(5.0, 12.0),
                weight=random.randint(1, 3),
                priority=random.randint(0, 2),
                release_time=random.randint(0, 180)
            ))
        return orders