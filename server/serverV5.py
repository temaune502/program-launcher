import socket
import threading
import json
import os
import ctypes
from pystray import Icon, MenuItem, Menu
from PIL import Image
import sys
clients = {}
console_clients = []
toggle_console_item = None  # Зберігаємо елемент меню глобально

# Отримання хендлу вікна консолі
def get_console_window():
    return ctypes.windll.kernel32.GetConsoleWindow()

# Функція для приховування консолі
def hide_console():
    hwnd = get_console_window()
    if hwnd != 0:
        ctypes.windll.user32.ShowWindow(hwnd, 0)

hide_console()  # Приховуємо консоль при запуску

# Функція для показу консолі
def show_console():
    hwnd = get_console_window()
    if hwnd != 0:
        ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW

# Функція для виходу з програми через трей
def quit_tray(icon, item):
    icon.stop()
    os._exit(0)

# Функція для перемикання стану видимості консолі
def toggle_console_visibility(icon, item):
    global toggle_console_item

    hwnd = get_console_window()
    if ctypes.windll.user32.IsWindowVisible(hwnd):
        hide_console()
        toggle_console_item = MenuItem('Відкрити консоль', toggle_console_visibility)
    else:
        show_console()
        toggle_console_item = MenuItem('Приховати консоль', toggle_console_visibility)

    icon.update_menu()

# Створення іконки для трея
def setup_tray():
    global toggle_console_item
    icon_image = Image.new('RGB', (64, 64), color=(45, 68, 135))  # Іконка для трея
    toggle_console_item = MenuItem('Приховати консоль', toggle_console_visibility)
    menu = Menu(
        toggle_console_item,
        MenuItem('Вийти', quit_tray)
    )
    icon = Icon('Server', icon_image, menu=menu)
    icon.run()

# Функція для введення команд в консолі
def console_input():
    while True:
        command = input(">").strip()

        if command == "list_clients":
            print("Клієнти на сервері:", list(clients.keys()))
        elif command == "exit":
            os._exit(0)
        elif command == "hide":
            hide_console()
        elif command.startswith("kick"):
            _, client_name = command.split(maxsplit=1)
            if client_name in clients:
                send_message(clients[client_name], "server", "disconnected")
                clients[client_name].close()
                del clients[client_name]
                print(f"Клієнт {client_name} від'єднаний.")
            else:
                print(f"Клієнт {client_name} не знайдений.")
        elif command.startswith("send"):
            _, client_name, *message = command.split(maxsplit=2)
            if client_name in clients:
                send_message(clients[client_name], "server", ' '.join(message))
                print(f"Повідомлення надіслане клієнту {client_name}.")
            else:
                print(f"Клієнт {client_name} не знайдений.")
        elif command == "cls":
            os.system('cls' if os.name == 'nt' else 'clear')
        else:
            print("Невідома команда.")

# Основна логіка обробки клієнтів
def handle_client(client_socket, addr, name):
    global clients, console_clients

    clients[name] = client_socket
    print(f"Client {name} connected from {addr}")
    client_socket.sendall(json.dumps({"status": "connected"}).encode('utf-8'))

    if name.startswith("console:"):
        console_clients.append(client_socket)
        print(f"Console client {name} connected")

    while True:
        try:
            data = client_socket.recv(1024).decode('utf-8').strip()
            if data.lower() == "exit":
                print(f"Client {name} disconnected")
                break

            if ":" in data:
                target_name, message = data.split(":", 1)
                target_name = target_name.strip()
                message = message.strip()

                if target_name == "server":
                    execute_server_command(name, message)
                elif target_name == "from_all":
                    broadcast_message(name, message)
                elif target_name in clients:
                    send_message(clients[target_name], name, message)
                else:
                    send_message(client_socket, "server", "client_not_found")

            notify_consoles(name, data)

        except ConnectionResetError:
            print(f"Client {name} unexpectedly disconnected")
            break

    client_socket.close()
    del clients[name]
    if client_socket in console_clients:
        console_clients.remove(client_socket)

def execute_server_command(sender_name, command):
    global clients
    command = command.strip().lower()

    if command == "list_clients":
        response = {"command": "list_clients", "clients": list(clients.keys())}
    elif command.startswith("kick_client"):
        _, client_name = command.split(maxsplit=1)
        if client_name in clients:
            send_message(clients[client_name], "server", "disconnected")
            clients[client_name].close()
            del clients[client_name]
            response = {"command": "kick_client", "status": "success", "client": client_name}
        else:
            response = {"command": "kick_client", "status": "client_not_found"}
    elif command == "shutdown":
        response = {"command": "shutdown", "status": "success"}
        broadcast_message("server", "shutdown")
        for client_socket in clients.values():
            client_socket.close()
        clients.clear()
        raise SystemExit(response)
    else:
        response = {"command": "unknown_command"}

    send_message(clients[sender_name], "server", response)

def broadcast_message(sender_name, message):
    global clients
    message_json = json.dumps({"from": sender_name, "message": message})
    for client_name, client_socket in clients.items():
        if client_name != sender_name:
            client_socket.sendall(message_json.encode('utf-8'))

def notify_consoles(sender_name, message):
    global console_clients
    notification_json = json.dumps({"from": sender_name, "message": message})
    for console_socket in console_clients:
        console_socket.sendall(notification_json.encode('utf-8'))

def send_message(client_socket, sender_name, message):
    if isinstance(message, dict):
        message_json = json.dumps({"from": sender_name, **message})
    else:
        message_json = json.dumps({"from": sender_name, "message": message})
    client_socket.sendall(message_json.encode('utf-8'))

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 65432))
    server_socket.listen()

    print("Server started and waiting for clients...")

    while True:
        client_socket, addr = server_socket.accept()
        client_socket.sendall(json.dumps({"request": "name"}).encode('utf-8'))
        name = client_socket.recv(1024).decode('utf-8').strip()
        client_thread = threading.Thread(target=handle_client, args=(client_socket, addr, name))
        client_thread.start()

if __name__ == "__main__":

    threading.Thread(target=start_server).start()  # Запуск сервера в окремому потоці
    threading.Thread(target=console_input).start()  # Запуск потоку для обробки команд з консолі
    console_input.daemon = True
    start_server.daemon = True
    setup_tray()  # Запуск трея
