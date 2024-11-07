import json
import keyboard
import threading
from UniClient import Client

# Завантаження конфігурації
def load_config(file_path='config.json'):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

# Обробник гарячих клавіш
def register_hotkeys(client, target_name, hotkeys):
    # Спочатку очищаємо всі поточні гарячі клавіші
    keyboard.unhook_all()

    # Прив'язка гарячих клавіш до функцій
    for hotkey, message in hotkeys.items():
        keyboard.add_hotkey(hotkey, lambda msg=message: client.send(target_name, msg))
    print("Гарячі клавіші зареєстровані заново.")

# Функція для перереєстрації комбінацій кожні 2 хвилини
def re_register_hotkeys(client, target_name, hotkeys, interval=120):
    def re_register():
        while True:
            register_hotkeys(client, target_name, hotkeys)
            threading.Event().wait(interval)

    threading.Thread(target=re_register, daemon=True).start()

# Головна функція
def main():
    # Завантаження конфігурації
    config = load_config()
    hotkeys = config["hotkeys"]
    target_name = config["target_name"]
    client_name = config["name"]

    # Ініціалізація клієнта
    client = Client(client_name)
    client.start()

    # Встановлення обробника гарячих клавіш
    register_hotkeys(client, target_name, hotkeys)

    # Запуск циклу для перереєстрації гарячих клавіш
    re_register_hotkeys(client, target_name, hotkeys)

    # Очікування натискання клавіш
    print("Натисніть гарячі клавіші для виконання відповідних дій (Ctrl+C для виходу).")
    keyboard.wait()  # Програма очікує подій

if __name__ == "__main__":
    main()
