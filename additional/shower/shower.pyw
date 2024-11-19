import subprocess
import json
import time
import psutil  # Потрібна бібліотека для роботи з процесами
import os
from UniClient import Client

# Змінюємо робочу директорію на ту, де розташований сам скрипт
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Ініціалізація клієнта для підключення до сервера
client = Client(name="shower")
launcher_message_sent = False

def get_config():
    # Зчитуємо налаштування з файлу config.json
    try:
        with open("config.json", "r") as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        print("Файл config.json не знайдено.")
        return None
    except json.JSONDecodeError:
        print("Помилка розпізнавання JSON у файлі config.json.")
        return None

def check_launcher_connection():
    global launcher_message_sent

    # Запитуємо список клієнтів на сервері
    client.send("server", "list_clients")
    time.sleep(0.5)  # Пауза для отримання відповіді від серверу
    messages = client.received_messages

    for msg in messages:
        try:
            data = json.loads(msg)
            # Перевіряємо, чи це відповідь від серверу із списком клієнтів
            if data.get("from") == "server" and data.get("command") == "list_clients":
                clients = data.get("clients", [])
                print(f"Підключені клієнти: {clients}")
                
                # Якщо клієнт 'launcher' підключений, надіслати команду для відображення інтерфейсу
                if "launcher" in clients:
                    print("Клієнт 'launcher' знайдений, надсилаємо команду для відображення інтерфейсу...")
                    client.send("launcher", "show_window")
                    launcher_message_sent = True
                else:
                    print("Клієнт 'launcher' не знайдений.")
                return "launcher_connected" if "launcher" in clients else "launcher_not_connected"
        except json.JSONDecodeError:
            print("Неможливо розпізнати повідомлення:", msg)
    return None

def is_launcher_process_running(process_name):
    # Перевірка, чи запущений процес з назвою з config.json
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    return False

def launch_launcher(path):
    # Запуск процесу ланчера у новій консолі з правильного розташування
    program_dir = os.path.dirname(path)
    try:
        subprocess.Popen(path, creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=program_dir)
        print("Лаунчер запущено.")
    except FileNotFoundError:
        print("Лаунчер не знайдено за вказаним шляхом.")

if __name__ == "__main__":
    client.start()
    config = get_config()
    
    if not config:
        exit()  # Якщо немає конфігурації, завершуємо скрипт

    # Крок 1 і 2: Перевіряємо підключення клієнта launcher
    status = check_launcher_connection()
    if status == "launcher_connected":
        exit()  # Якщо launcher підключений, скрипт завершується після надсилання команди

    # Крок 3: Перевірка налаштування start_launcher
    if not config.get("start_launcher", False):
        print("start_launcher вимкнено в конфігурації. Завершення скрипта.")
        exit()

    # Крок 4: Перевірка процесу лаунчера
    launcher_process_name = config.get("launcher_process_name")
    if launcher_process_name and is_launcher_process_running(launcher_process_name):
        print("Процес лаунчера вже запущений, але не підключений до серверу. Завершення скрипта.")
        exit()

    # Крок 5: Запуск лаунчера, якщо його немає
    launcher_path = config.get("launcher_path")
    if launcher_path:
        launch_launcher(launcher_path)
    else:
        print("Шлях до лаунчера не вказано в конфігурації. Завершення скрипта.")
