# systems/weather.py
import random
import time
import math
from collections import deque


class EnhancedWeatherSystem:
    TRANSITION_MATRIX = {
        'clear': {'clear': 0.4, 'clouds': 0.3, 'wind': 0.2, 'heat': 0.1},
        'clouds': {'clear': 0.2, 'clouds': 0.3, 'rain_light': 0.3, 'fog': 0.2},
        'rain_light': {'clouds': 0.3, 'rain_light': 0.2, 'rain': 0.3, 'clear': 0.2},
        'rain': {'rain_light': 0.3, 'rain': 0.2, 'storm': 0.2, 'clouds': 0.3},
        'storm': {'rain': 0.4, 'storm': 0.2, 'clouds': 0.4},
        'fog': {'fog': 0.3, 'clouds': 0.4, 'clear': 0.3},
        'wind': {'wind': 0.2, 'clear': 0.3, 'clouds': 0.3, 'cold': 0.2},
        'heat': {'heat': 0.3, 'clear': 0.4, 'clouds': 0.3},
        'cold': {'cold': 0.3, 'clear': 0.2, 'clouds': 0.3, 'wind': 0.2}
    }

    SPEED_MULTIPLIERS = {
        'clear': 1.00, 'clouds': 0.98, 'rain_light': 0.90, 'rain': 0.85,
        'storm': 0.75, 'fog': 0.88, 'wind': 0.92, 'heat': 0.90, 'cold': 0.92
    }

    STAMINA_PENALTIES = {
        'clear': 0.0, 'clouds': 0.0, 'rain_light': 0.05, 'rain': 0.1,
        'storm': 0.3, 'fog': 0.0, 'wind': 0.1, 'heat': 0.2, 'cold': 0.05
    }

    WEATHER_COLORS = {
        'clear': (200, 150, 100), 'clouds': (180, 180, 180),
        'rain_light': (100, 150, 200), 'rain': (70, 120, 180),
        'storm': (50, 50, 100), 'fog': (200, 200, 200),
        'wind': (150, 200, 150), 'heat': (255, 100, 100),
        'cold': (150, 200, 255)
    }

    def __init__(self):
        self.current_condition = 'clear'
        self.current_intensity = 0.5
        self.time_in_current = 0
        self.burst_duration = 30
        self.weather_memory = deque(maxlen=5)
        self.transitioning = False
        self.transition_start_time = 0
        self.transition_duration = 3.0
        self.previous_condition = 'clear'
        self.previous_intensity = 0.5
        self.target_condition = 'clear'
        self.target_intensity = 0.5
        self.weather_notifications = []
        self.notification_timer = 0

    def update(self, dt: float):
        self.time_in_current += dt
        self.notification_timer += dt
        self.weather_notifications = [
            (msg, time_left - dt) for msg, time_left in self.weather_notifications
            if time_left - dt > 0
        ]

        if self.transitioning:
            elapsed_transition = time.time() - self.transition_start_time
            progress = min(1.0, elapsed_transition / self.transition_duration)
            smooth_progress = (1 - math.cos(progress * math.pi)) / 2
            self.current_intensity = self.previous_intensity + (
                        self.target_intensity - self.previous_intensity) * smooth_progress

            if progress >= 1.0:
                self.transitioning = False
                self.current_condition = self.target_condition
                self.current_intensity = self.target_intensity
                effect_desc = self._get_weather_effect_description()
                self.weather_notifications.append((f"🌦️ {self.get_weather_description()} - {effect_desc}", 4.0))

        if self.time_in_current >= self.burst_duration and not self.transitioning:
            self._initiate_weather_change()

    def _initiate_weather_change(self):
        transitions = self.TRANSITION_MATRIX.get(self.current_condition, {'clear': 1.0})
        conditions = list(transitions.keys())
        weights = list(transitions.values())

        new_condition = random.choices(conditions, weights=weights)[0]
        new_intensity = random.uniform(0.4, 0.9)

        self.transitioning = True
        self.transition_start_time = time.time()
        self.previous_condition = self.current_condition
        self.previous_intensity = self.current_intensity
        self.target_condition = new_condition
        self.target_intensity = new_intensity

        self.time_in_current = 0
        self.burst_duration = random.randint(25, 40)
        self.weather_memory.append(new_condition)

        transition_desc = f"Cambiando de {self._get_condition_name(self.previous_condition)} a {self._get_condition_name(new_condition)}"
        self.weather_notifications.append((f"⚡ {transition_desc}", 3.0))

    def _get_condition_name(self, condition: str) -> str:
        names = {
            'clear': 'Despejado', 'clouds': 'Nublado', 'rain_light': 'Llovizna',
            'rain': 'Lluvia', 'storm': 'Tormenta', 'fog': 'Niebla',
            'wind': 'Viento', 'heat': 'Calor', 'cold': 'Frío'
        }
        return names.get(condition, condition)

    def _get_weather_effect_description(self) -> str:
        speed_mult = self.get_speed_multiplier()
        stamina_penalty = self.get_stamina_penalty()

        if speed_mult < 0.8:
            speed_desc = "Velocidad muy reducida"
        elif speed_mult < 0.9:
            speed_desc = "Velocidad reducida"
        elif speed_mult < 0.95:
            speed_desc = "Velocidad ligeramente reducida"
        else:
            speed_desc = "Velocidad normal"

        if stamina_penalty > 0.2:
            stamina_desc = "Resistencia se agota muy rápido"
        elif stamina_penalty > 0.1:
            stamina_desc = "Resistencia se agota más rápido"
        elif stamina_penalty > 0.05:
            stamina_desc = "Resistencia se agota un poco más rápido"
        else:
            stamina_desc = "Resistencia normal"

        return f"{speed_desc} | {stamina_desc}"

    def get_speed_multiplier(self) -> float:
        if self.transitioning:
            elapsed_transition = time.time() - self.transition_start_time
            progress = min(1.0, elapsed_transition / self.transition_duration)
            smooth_progress = (1 - math.cos(progress * math.pi)) / 2
            prev_mult = self.SPEED_MULTIPLIERS[self.previous_condition]
            target_mult = self.SPEED_MULTIPLIERS[self.target_condition]
            base_mult = prev_mult + (target_mult - prev_mult) * smooth_progress
        else:
            base_mult = self.SPEED_MULTIPLIERS[self.current_condition]

        return base_mult * (1.0 - (self.current_intensity * 0.2))

    def get_stamina_penalty(self) -> float:
        if self.transitioning:
            elapsed_transition = time.time() - self.transition_start_time
            progress = min(1.0, elapsed_transition / self.transition_duration)
            smooth_progress = (1 - math.cos(progress * math.pi)) / 2
            prev_penalty = self.STAMINA_PENALTIES[self.previous_condition]
            target_penalty = self.STAMINA_PENALTIES[self.target_condition]
            base_penalty = prev_penalty + (target_penalty - prev_penalty) * smooth_progress
        else:
            base_penalty = self.STAMINA_PENALTIES[self.current_condition]

        return base_penalty * self.current_intensity

    def get_weather_description(self) -> str:
        condition_to_use = self.target_condition if self.transitioning else self.current_condition
        base_desc = self._get_condition_name(condition_to_use)

        if self.transitioning:
            base_desc += " (Cambiando)"

        if self.current_intensity >= 0.8:
            return f"{base_desc} (Intenso)"
        elif self.current_intensity >= 0.6:
            return f"{base_desc} (Moderado)"
        else:
            return f"{base_desc} (Leve)"

    def get_weather_color(self) -> tuple:
        condition_to_use = self.target_condition if self.transitioning else self.current_condition
        return self.WEATHER_COLORS.get(condition_to_use, (255, 255, 255))