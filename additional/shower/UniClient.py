import socket
import threading

class Client:
    def __init__(self, name, server_host='localhost', server_port=65432):
        self.name = name
        self.server_host = server_host
        self.server_port = server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(5)  # Таймаут для підключення
        self.received_messages = []  # Змінна для збереження отриманих повідомлень
        self.is_connected = False

    def start(self):
        try:
            # Перевірка, чи вже підключений
            if not self.is_connected:
                self.client_socket.connect((self.server_host, self.server_port))
                self.client_socket.sendall(self.name.encode('utf-8'))
                self.is_connected = True
                print("Connected to server")
                
                # Запускаємо потік для отримання повідомлень
                threading.Thread(target=self.receive_messages, daemon=True).start()
        except (socket.timeout, ConnectionRefusedError) as e:
            print(f"Connecting error: {e}. Retrying...")
            self.reconnect()
        except Exception as e:
            print(f"Unexpected error: {e}")

    def restart_connection(self):
        """Функція для примусового перезапуску з'єднання"""
        print("Restarting connection...")
        if self.is_connected:
            self.close()  # Закриваємо поточне з'єднання
        self.start()  # Відновлюємо нове з'єднання
    
    
    def reconnect(self):
        if not self.is_connected:
            try:
                # Створюємо новий сокет і пробуємо знову підключитися
                self.client_socket.close()
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5)
                print("Attempting to reconnect...")
                self.start()  # Викликаємо спробу знову підключитися
            except Exception as e:
                print(f"Reconnect error: {e}")

    def receive_messages(self):
        while self.is_connected:
            try:
                data = self.client_socket.recv(1024).decode('utf-8')
                if data:
                    self.received_messages.append(data)  # Зберігаємо отримане повідомлення у список
                else:
                    print("Server disconnected")
                    self.is_connected = False
                    self.reconnect()
                    break
            except socket.timeout:
                # Таймаут може виникнути без втрати підключення, тому не відразу скидаємо з'єднання
                continue
            except Exception as e:
                print(f"Error receiving message: {e}")
                self.is_connected = False
                self.reconnect()
                break

    def send(self, target_name, message):
        try:
            if self.is_connected:
                formatted_message = f"{target_name}: {message}"
                self.client_socket.sendall(formatted_message.encode('utf-8'))
            else:
                print("Cannot send message, not connected to server.")
        except Exception as e:
            print(f"Error sending message: {e}")

    def close(self):
        self.is_connected = False
        self.client_socket.close()

# Приклад використання
# client = Client(name="Client1")
# client.start()
# Надсилання повідомлення
# client.send("Client2", "Привіт!")
# Закриття клієнта
# client.close()
