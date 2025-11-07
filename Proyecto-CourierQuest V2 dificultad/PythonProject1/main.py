# main.py

"""Courier Quest """
from game import CourierQuest


def main():
    """Función principal del programa."""
    print("=" * 90)
    print("  COURIER QUEST")
    print("  Proyecto EIF-207 Estructuras de Datos")
    print("  API  ")
    print("=" * 90)
    print()

    try:
        game = CourierQuest()
        game.run()

    except Exception as e:
        print(f"Error ejecutando el juego: {e}")
        import traceback
        traceback.print_exc()
        input("Presiona ENTER para salir...")


if __name__ == "__main__":
    main()