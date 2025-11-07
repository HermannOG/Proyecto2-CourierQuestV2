# ui/menu.py
import pygame
from typing import Optional
from systems.file_manager import RobustFileManager
from config.constants import WINDOW_WIDTH, WINDOW_HEIGHT, UI_HIGHLIGHT, UI_BORDER


class GameMenu:
    def __init__(self):
        self.state = "main_menu"
        self.main_options = ["Nuevo Juego (Solo)", "Jugar vs CPU", "Cargar Partida", "Tutorial", "Ver Puntajes", "Salir"]
        self.difficulty_options = ["Fácil", "Medio", "Difícil", "Volver"]
        self.selected = 0
        self.selected_difficulty = "medium"  # Dificultad por defecto
        self.file_manager = RobustFileManager()

        # Fuentes para el menú principal (más grandes)
        self.title_font = pygame.font.Font(None, 72)
        self.menu_font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 32)

        # Fuentes para submenús (tamaño original)
        self.submenu_title_font = pygame.font.Font(None, 48)
        self.submenu_font = pygame.font.Font(None, 32)
        self.submenu_small_font = pygame.font.Font(None, 24)

        # Cargar imágenes de los repartidores
        self.courier_left = None
        self.courier_right = None


    def handle_menu_input(self, event) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if self.state == "main_menu":
                return self._handle_main_menu_input(event)
            elif self.state == "difficulty_menu":
                return self._handle_difficulty_menu_input(event)
            elif self.state == "load_menu":
                return self._handle_load_menu_input(event)
            elif self.state == "scores_menu":
                return self._handle_scores_menu_input(event)
        return None

    def _handle_scores_menu_input(self, event) -> Optional[str]:
        if event.key in (pygame.K_b, pygame.K_ESCAPE, pygame.K_RETURN):
            self.state = "main_menu"
            self.selected = 3
            if hasattr(self, '_cached_scores'):
                self._cached_scores = None
        return None

    def _handle_main_menu_input(self, event) -> Optional[str]:
        if event.key == pygame.K_UP:
            self.selected = (self.selected - 1) % len(self.main_options)
            if hasattr(self, '_cached_scores'):
                self._cached_scores = None
        elif event.key == pygame.K_DOWN:
            self.selected = (self.selected + 1) % len(self.main_options)
            if hasattr(self, '_cached_scores'):
                self._cached_scores = None
        elif event.key == pygame.K_RETURN:
            option = self.main_options[self.selected]
            if option == "Nuevo Juego (Solo)":
                return "start_new_game"
            elif option == "Jugar vs CPU":
                self.state = "difficulty_menu"
                self.selected = 1  # Medio por defecto
                if hasattr(self, '_cached_scores'):
                    self._cached_scores = None
            elif option == "Cargar Partida":
                self.state = "load_menu"
                self.selected = 0
                if hasattr(self, '_cached_scores'):
                    self._cached_scores = None
            elif option == "Tutorial":
                return "start_tutorial"
            elif option == "Ver Puntajes":
                self.state = "scores_menu"
                self.selected = 0
            elif option == "Salir":
                return "exit"
        elif event.key == pygame.K_ESCAPE:
            return "exit"
        return None

    def _handle_difficulty_menu_input(self, event) -> Optional[str]:
        """Maneja la entrada en el menú de selección de dificultad."""
        if event.key == pygame.K_UP:
            self.selected = (self.selected - 1) % len(self.difficulty_options)
        elif event.key == pygame.K_DOWN:
            self.selected = (self.selected + 1) % len(self.difficulty_options)
        elif event.key == pygame.K_RETURN:
            option = self.difficulty_options[self.selected]
            if option == "Fácil":
                self.selected_difficulty = "easy"
                return "start_vs_cpu"
            elif option == "Medio":
                self.selected_difficulty = "medium"
                return "start_vs_cpu"
            elif option == "Difícil":
                self.selected_difficulty = "hard"
                return "start_vs_cpu"
            elif option == "Volver":
                self.state = "main_menu"
                self.selected = 1  # Volver a "Jugar vs CPU"
        elif event.key in (pygame.K_b, pygame.K_ESCAPE):
            self.state = "main_menu"
            self.selected = 1
        return None

    def _handle_load_menu_input(self, event) -> Optional[str]:
        if event.key == pygame.K_UP:
            self.selected = max(0, self.selected - 1)
        elif event.key == pygame.K_DOWN:
            self.selected = min(1, self.selected + 1)
        elif event.key == pygame.K_RETURN:
            if self.selected == 1:
                self.state = "main_menu"
                self.selected = 1
            else:
                return "load_slot_1"
        elif event.key in (pygame.K_b, pygame.K_ESCAPE):
            self.state = "main_menu"
            self.selected = 1
        return None

    def draw(self, screen):
        screen.fill((20, 25, 40))

        if self.state == "main_menu":
            self._draw_main_menu(screen)
        elif self.state == "difficulty_menu":
            self._draw_difficulty_menu(screen)
        elif self.state == "load_menu":
            self._draw_load_menu(screen)
        elif self.state == "scores_menu":
            self._draw_scores_menu(screen)

    def _draw_scores_menu(self, screen):
        title = self.submenu_title_font.render("TABLA DE PUNTAJES", True, (255, 255, 255))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 80))
        screen.blit(title, title_rect)

        if not hasattr(self, '_cached_scores') or self._cached_scores is None:
            self._cached_scores = self.file_manager.load_scores()

        scores = self._cached_scores

        if not scores:
            no_scores_text = self.submenu_font.render("No hay puntajes registrados", True, (150, 150, 150))
            text_rect = no_scores_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            screen.blit(no_scores_text, text_rect)
        else:
            start_y = 150
            headers = ["#", "Puntaje", "Dinero", "Rep.", "Pedidos", "Fecha", "Estado"]
            header_positions = [100, 200, 320, 420, 520, 650, 850]

            for i, header in enumerate(headers):
                header_text = self.submenu_font.render(header, True, (200, 200, 255))
                screen.blit(header_text, (header_positions[i], start_y))

            pygame.draw.line(screen, (100, 100, 150), (80, start_y + 35), (WINDOW_WIDTH - 80, start_y + 35), 2)

            for i, score in enumerate(scores[:10]):
                y_pos = start_y + 50 + i * 35
                rank_color = (255, 215, 0) if i == 0 else (192, 192, 192) if i == 1 else (205, 127, 50) if i == 2 else (
                    255, 255, 255)

                rank_text = self.submenu_small_font.render(f"{i + 1}", True, rank_color)
                screen.blit(rank_text, (header_positions[0], y_pos))

                score_text = self.submenu_small_font.render(f"{score.get('score', 0)}", True, rank_color)
                screen.blit(score_text, (header_positions[1], y_pos))

                money_text = self.submenu_small_font.render(f"${score.get('money', 0)}", True, (100, 255, 100))
                screen.blit(money_text, (header_positions[2], y_pos))

                rep = score.get('reputation', 0)
                rep_color = (100, 255, 100) if rep >= 80 else (255, 255, 100) if rep >= 50 else (255, 100, 100)
                rep_text = self.submenu_small_font.render(f"{rep}", True, rep_color)
                screen.blit(rep_text, (header_positions[3], y_pos))

                orders_text = self.submenu_small_font.render(f"{score.get('completed_orders', 0)}", True,
                                                             (150, 200, 255))
                screen.blit(orders_text, (header_positions[4], y_pos))

                date_str = score.get('date', '')[:16].replace('T', ' ')
                date_text = self.submenu_small_font.render(date_str, True, (150, 150, 150))
                screen.blit(date_text, (header_positions[5], y_pos))

                victory = score.get('victory', False)
                status_text = "VICTORIA" if victory else "DERROTA"
                status_color = (100, 255, 100) if victory else (255, 100, 100)
                status_surface = self.submenu_small_font.render(status_text, True, status_color)
                screen.blit(status_surface, (header_positions[6], y_pos))

        back_text = self.submenu_small_font.render("Presiona B, ESC o ENTER para volver", True, (150, 150, 150))
        back_rect = back_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 50))
        screen.blit(back_text, back_rect)

    def _draw_main_menu(self, screen):
        # Título
        title = self.title_font.render("COURIER QUEST", True, (255, 255, 255))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 150))
        screen.blit(title, title_rect)

        subtitle = self.menu_font.render("API REAL INTEGRADA - EIF-207", True, (100, 255, 100))
        subtitle_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 220))
        screen.blit(subtitle, subtitle_rect)

        # Opciones del menú (más espaciadas por el tamaño mayor)
        start_y = 320
        for i, option in enumerate(self.main_options):
            color = (255, 255, 100) if i == self.selected else (255, 255, 255)
            text = self.menu_font.render(option, True, color)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, start_y + i * 65))

            if i == self.selected:
                pygame.draw.rect(screen, (50, 50, 100),
                                 (text_rect.x - 20, text_rect.y - 5, text_rect.width + 40, text_rect.height + 10))

            screen.blit(text, text_rect)

        instructions = self.small_font.render("Usa las flechas para navegar, ENTER para seleccionar", True, (150, 150, 150))
        instructions_rect = instructions.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 50))
        screen.blit(instructions, instructions_rect)

    def _draw_difficulty_menu(self, screen):
        """Dibuja el menú de selección de dificultad."""
        # Título
        title = self.submenu_title_font.render("SELECCIONAR DIFICULTAD", True, (255, 255, 255))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 120))
        screen.blit(title, title_rect)

        # Subtítulo
        subtitle = self.submenu_small_font.render("Elige el nivel de desafío para el CPU", True, (150, 200, 255))
        subtitle_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 170))
        screen.blit(subtitle, subtitle_rect)

        # Descripciones de dificultad
        descriptions = {
            "Fácil": "Movimientos aleatorios - Ideal para principiantes",
            "Medio": "Búsqueda Greedy con heurísticas - Desafío equilibrado",
            "Difícil": "Algoritmos A* y TSP - Rival experto",
            "Volver": "Regresar al menú principal"
        }

        # Opciones
        start_y = 250
        for i, option in enumerate(self.difficulty_options):
            is_selected = i == self.selected

            # Color según selección
            color = (255, 255, 100) if is_selected else (255, 255, 255)
            desc_color = (200, 200, 100) if is_selected else (150, 150, 150)

            # Dibujar fondo si está seleccionado
            option_text = self.submenu_font.render(option, True, color)
            text_rect = option_text.get_rect(center=(WINDOW_WIDTH // 2, start_y + i * 100))

            if is_selected:
                bg_rect = pygame.Rect(
                    text_rect.x - 30, text_rect.y - 10,
                    text_rect.width + 60, text_rect.height + 50
                )
                pygame.draw.rect(screen, (50, 50, 100), bg_rect, border_radius=10)
                pygame.draw.rect(screen, (100, 100, 200), bg_rect, 2, border_radius=10)

            # Dibujar texto de opción
            screen.blit(option_text, text_rect)

            # Dibujar descripción
            desc_text = self.submenu_small_font.render(descriptions[option], True, desc_color)
            desc_rect = desc_text.get_rect(center=(WINDOW_WIDTH // 2, start_y + i * 100 + 25))
            screen.blit(desc_text, desc_rect)

        # Instrucciones
        instructions = self.submenu_small_font.render(
            "↑↓ Navegar | ENTER Seleccionar | ESC Volver",
            True, (150, 150, 150)
        )
        instructions_rect = instructions.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 50))
        screen.blit(instructions, instructions_rect)

    def _draw_load_menu(self, screen):
        title = self.submenu_title_font.render("CARGAR PARTIDA", True, (255, 255, 255))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 100))
        screen.blit(title, title_rect)

        start_y = 250
        slot_info = self.file_manager.get_save_info(1)

        if self.selected == 0:
            color = (255, 255, 100)
            bg_color = (50, 50, 100)
        elif slot_info:
            color = (255, 255, 255)
            bg_color = (30, 30, 50)
        else:
            color = (100, 100, 100)
            bg_color = (20, 20, 30)

        slot_rect = pygame.Rect(WINDOW_WIDTH // 2 - 300, start_y - 5, 600, 70)
        pygame.draw.rect(screen, bg_color, slot_rect)
        pygame.draw.rect(screen, color, slot_rect, 2)

        if slot_info:
            slot_text = f"Slot 1 - {slot_info.get('saved_at', 'Desconocido')[:19]}"
            progress_text = f"Progreso: {slot_info.get('completion_percentage', 0):.1f}%"
            city_text = slot_info.get('city_info', 'Ciudad desconocida')

            slot_label = self.submenu_font.render(slot_text, True, color)
            progress_label = self.submenu_small_font.render(progress_text, True, color)
            city_label = self.submenu_small_font.render(city_text, True, color)

            screen.blit(slot_label, (WINDOW_WIDTH // 2 - 280, start_y))
            screen.blit(progress_label, (WINDOW_WIDTH // 2 - 280, start_y + 25))
            screen.blit(city_label, (WINDOW_WIDTH // 2 - 280, start_y + 45))
        else:
            empty_text = "Slot 1 - Vacío"
            empty_label = self.submenu_font.render(empty_text, True, color)
            screen.blit(empty_label, (WINDOW_WIDTH // 2 - 280, start_y + 20))

        volver_color = (255, 255, 100) if self.selected == 1 else (255, 255, 255)
        volver_text = self.submenu_font.render("← Volver al menú principal (B)", True, volver_color)
        volver_rect = volver_text.get_rect(center=(WINDOW_WIDTH // 2, start_y + 120))

        if self.selected == 1:
            pygame.draw.rect(screen, (50, 50, 100),
                             (volver_rect.x - 20, volver_rect.y - 5, volver_rect.width + 40, volver_rect.height + 10))

        screen.blit(volver_text, volver_rect)