# systems/file_manager.py - VERSIÓN CORREGIDA CON SLOTS
import os
import json
import pickle
import time
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from models.game_state import GameState


class RobustFileManager:
    """Gestor de archivos robusto con sistema de slots de guardado."""

    def __init__(self):
        self._ensure_directory_structure()

    def _ensure_directory_structure(self):
        """Crea la estructura de directorios necesaria."""
        directories = ['data', 'saves', 'api_cache', 'backups']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def save_game_with_validation(self, game_state: GameState, slot: int = 1) -> bool:
        """
        Guarda el juego en un slot específico con validación completa.

        Args:
            game_state: Estado actual del juego
            slot: Número de slot (1-3 recomendado)

        Returns:
            True si se guardó correctamente, False en caso contrario
        """
        try:
            # ✅ Crear archivo de guardado con slot
            save_file = f"saves/slot{slot}.sav"

            # ✅ Crear datos de guardado con metadatos
            save_data = {
                'version': '3.2_slots_fixed',
                'timestamp': time.time(),
                'game_state': game_state,
                'metadata': {
                    'saved_at': datetime.now().isoformat(),
                    'game_time': game_state.game_time,
                    'player_position': (game_state.player_pos.x, game_state.player_pos.y),
                    'completion_percentage': (game_state.money / game_state.goal) * 100,
                    'city_info': f"{game_state.city_name} ({game_state.city_width}x{game_state.city_height})",
                    'slot': slot
                }
            }

            if os.path.exists(save_file):
                backup_file = f"backups/slot{slot}_backup_{int(time.time())}.sav"
                try:
                    shutil.copy2(save_file, backup_file)

                    # Mantener solo los últimos 3 backups por slot
                    self._cleanup_old_backups(slot, max_backups=3)
                except Exception as e:
                    print(f"⚠️ No se pudo crear backup: {e}")

            # ✅ Guardar con pickle de alta compatibilidad
            with open(save_file, 'wb') as f:
                pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)

            print(f"💾 Juego guardado en slot {slot}")
            print(f"   📍 Posición: ({game_state.player_pos.x}, {game_state.player_pos.y})")
            print(f"   💰 Dinero: ${game_state.money}/{game_state.goal}")
            print(f"   ⭐ Reputación: {game_state.reputation}/100")

            return True

        except Exception as e:
            print(f"❌ Error guardando en slot {slot}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_game_with_validation(self, slot: int = 1) -> Optional[GameState]:
        """
        Carga el juego desde un slot específico con validación.

        Args:
            slot: Número de slot a cargar

        Returns:
            GameState si se cargó correctamente, None en caso contrario
        """
        save_file = f"saves/slot{slot}.sav"

        if not os.path.exists(save_file):
            print(f"⚠️ No existe guardado en slot {slot}")
            return None

        try:
            # ✅ Cargar archivo
            with open(save_file, 'rb') as f:
                save_data = pickle.load(f)

            # ✅ Validar estructura
            if not isinstance(save_data, dict):
                print(f"❌ Formato inválido en slot {slot}")
                return None

            if 'game_state' not in save_data:
                print(f"❌ Datos de juego no encontrados en slot {slot}")
                return None

            game_state = save_data['game_state']

            # ✅ Validar que tenga los atributos necesarios
            required_attrs = ['city_width', 'city_height', 'player_pos', 'money', 'goal']
            for attr in required_attrs:
                if not hasattr(game_state, attr):
                    print(f"❌ Atributo faltante: {attr}")
                    return None

            print(f"📂 Juego cargado desde slot {slot}")

            # Mostrar información del guardado
            if 'metadata' in save_data:
                meta = save_data['metadata']
                print(f"   📅 Guardado: {meta.get('saved_at', 'Desconocido')[:19]}")
                print(f"   🏙️ Ciudad: {meta.get('city_info', 'Desconocida')}")
                print(f"   📊 Progreso: {meta.get('completion_percentage', 0):.1f}%")

            return game_state

        except Exception as e:
            print(f"❌ Error cargando slot {slot}: {e}")
            import traceback
            traceback.print_exc()

            # ✅ Intentar recuperar desde backup
            return self._try_restore_from_backup(slot)

    def _try_restore_from_backup(self, slot: int) -> Optional[GameState]:
        """Intenta restaurar desde el backup más reciente."""
        try:
            backup_files = [
                f for f in os.listdir('backups')
                if f.startswith(f'slot{slot}_backup_') and f.endswith('.sav')
            ]

            if not backup_files:
                return None

            # Ordenar por timestamp (más reciente primero)
            backup_files.sort(reverse=True)
            latest_backup = os.path.join('backups', backup_files[0])

            print(f"🔄 Intentando restaurar desde backup: {backup_files[0]}")

            with open(latest_backup, 'rb') as f:
                save_data = pickle.load(f)

            if isinstance(save_data, dict) and 'game_state' in save_data:
                print("✅ Restauración desde backup exitosa")
                return save_data['game_state']

        except Exception as e:
            print(f"❌ No se pudo restaurar desde backup: {e}")

        return None

    def _cleanup_old_backups(self, slot: int, max_backups: int = 3):
        """Elimina backups antiguos, manteniendo solo los más recientes."""
        try:
            backup_files = [
                f for f in os.listdir('backups')
                if f.startswith(f'slot{slot}_backup_') and f.endswith('.sav')
            ]

            if len(backup_files) <= max_backups:
                return

            # Ordenar por timestamp
            backup_files.sort()

            # Eliminar los más antiguos
            for old_backup in backup_files[:-max_backups]:
                try:
                    os.remove(os.path.join('backups', old_backup))
                except:
                    pass

        except Exception as e:
            print(f"⚠️ Error limpiando backups: {e}")

    def get_save_info(self, slot: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene información sobre un guardado sin cargarlo completamente.

        Args:
            slot: Número de slot

        Returns:
            Diccionario con metadata del guardado o None
        """
        save_file = f"saves/slot{slot}.sav"

        if not os.path.exists(save_file):
            return None

        try:
            with open(save_file, 'rb') as f:
                save_data = pickle.load(f)

            if isinstance(save_data, dict) and 'metadata' in save_data:
                return save_data['metadata']

        except Exception as e:
            print(f"⚠️ Error leyendo info de slot {slot}: {e}")

        return None

    def list_all_saves(self) -> List[Dict[str, Any]]:
        """Lista todos los guardados disponibles con su información."""
        saves = []

        for slot in range(1, 4):  # Slots 1-3
            info = self.get_save_info(slot)
            if info:
                info['slot'] = slot
                saves.append(info)

        return saves

    def delete_save(self, slot: int) -> bool:
        """Elimina un guardado de un slot específico."""
        save_file = f"saves/slot{slot}.sav"

        try:
            if os.path.exists(save_file):
                os.remove(save_file)
                print(f"🗑️ Guardado en slot {slot} eliminado")
                return True
            return False
        except Exception as e:
            print(f"❌ Error eliminando slot {slot}: {e}")
            return False

    def load_scores(self) -> List[Dict[str, Any]]:
        """Carga la tabla de puntajes."""
        scores_file = "data/puntajes.json"

        try:
            os.makedirs("data", exist_ok=True)

            if not os.path.exists(scores_file):
                with open(scores_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
                return []

            with open(scores_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                scores = json.loads(content)

            if not isinstance(scores, list):
                return []

            scores.sort(key=lambda x: x.get('score', 0), reverse=True)
            return scores[:10]  # Top 10

        except Exception as e:
            print(f" Error cargando puntajes: {e}")
            return []

    def save_score(self, score_data: Dict[str, Any]) -> bool:
        """Guarda un nuevo puntaje en la tabla."""
        scores_file = "data/puntajes.json"

        try:
            scores = self.load_scores()

            scores.append(score_data)

            scores.sort(key=lambda x: x.get('score', 0), reverse=True)
            scores = scores[:10]

            # Guardar
            with open(scores_file, 'w', encoding='utf-8') as f:
                json.dump(scores, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f" Error guardando puntaje: {e}")
            return False