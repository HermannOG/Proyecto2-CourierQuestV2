# ui/tutorial.py
import pygame
from config.constants import WINDOW_WIDTH, WINDOW_HEIGHT


class TutorialSystem:
    def __init__(self):
        self.tutorial_steps = [
            {
                "title": "Bienvenido a Courier Quest",
                "message": "Eres un repartidor en bicicleta conectado a la API real de TigerCity. Tu objetivo es ganar $3000 antes de que termine la jornada laboral.",
                "keys": ["ENTER para continuar"]
            },
            {
                "title": "Movimiento Básico",
                "message": "Usa WASD o las flechas para moverte por la ciudad. Solo puedes moverte por calles (grises) y parques. Los edificios están bloqueados.",
                "keys": ["WASD o ↑↓←→ para moverse", "ENTER para continuar"]
            },
            {
                "title": "Resistencia y Estados",
                "message": "Tu resistencia (0-100) baja al moverte. Si llega a 0, quedas exhausto. Recupera hasta 30 para moverte de nuevo. Los parques te ayudan a recuperar más rápido.",
                "keys": ["Resistencia >30: Normal", "10-30: Cansado (x0.8 velocidad)", "≤0: Exhausto (no te mueves)"]
            },
            {
                "title": "Gestión de Pedidos",
                "message": "Presiona O para ver pedidos disponibles, I para inventario. Usa E en puntos de recogida y entrega. Los pedidos NO aparecen en edificios bloqueados.",
                "keys": ["O: Ver pedidos", "I: Inventario", "E: Interactuar", "ENTER para continuar"]
            },
            {
                "title": "Algoritmos de Ordenamiento",
                "message": "Usa algoritmos para organizar pedidos: P (QuickSort por prioridad), T (MergeSort por tiempo), D (Insertion Sort por distancia).",
                "keys": ["P: Ordenar por prioridad", "T: Ordenar por tiempo", "L: Ordenar por distancia",
                         "ENTER para comenzar"]
            }
        ]

        self.current_step = 0
        self.tutorial_active = True
        self.font = pygame.font.Font(None, 28)
        self.title_font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 20)

    def handle_input(self, event) -> bool:
        if not self.tutorial_active:
            return False

        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.current_step += 1
            if self.current_step >= len(self.tutorial_steps):
                self.tutorial_active = False
                return False

        return True

    def draw(self, screen):
        if not self.tutorial_active or self.current_step >= len(self.tutorial_steps):
            return

        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        step = self.tutorial_steps[self.current_step]

        panel_width = 900
        panel_height = 500
        panel_x = (WINDOW_WIDTH - panel_width) // 2
        panel_y = (WINDOW_HEIGHT - panel_height) // 2

        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(screen, (40, 50, 70), panel_rect, border_radius=15)
        pygame.draw.rect(screen, (100, 150, 200), panel_rect, 3, border_radius=15)

        title = self.title_font.render(step["title"], True, (255, 255, 255))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, panel_y + 50))
        screen.blit(title, title_rect)

        self._draw_wrapped_text(screen, step["message"],
                                panel_x + 40, panel_y + 100,
                                panel_width - 80, self.font, (220, 220, 220))

        controls_y = panel_y + panel_height - 150
        for i, key_info in enumerate(step["keys"]):
            key_text = self.small_font.render(f"• {key_info}", True, (150, 200, 255))
            screen.blit(key_text, (panel_x + 40, controls_y + i * 25))

        progress_text = f"Paso {self.current_step + 1} de {len(self.tutorial_steps)}"
        progress = self.small_font.render(progress_text, True, (150, 150, 150))
        progress_rect = progress.get_rect(center=(WINDOW_WIDTH // 2, panel_y + panel_height - 20))
        screen.blit(progress, progress_rect)

    def _draw_wrapped_text(self, surface, text, x, y, max_width, font, color):
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)

        if current_line:
            lines.append(' '.join(current_line))

        for i, line in enumerate(lines):
            line_surface = font.render(line, True, color)
            surface.blit(line_surface, (x, y + i * (font.get_height() + 5)))

    def is_active(self) -> bool:
        return self.tutorial_active