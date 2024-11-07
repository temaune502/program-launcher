from UniClient import Client
import json
import time

client = Client(name="shower")
message_counter = 0  # Лічильник повідомлень
launcher_message_sent = False  # Флаг для перевірки, чи було надіслано повідомлення

def check_for_launcher():
    global message_counter, launcher_message_sent

    # Надсилаємо повідомлення серверу для отримання списку клієнтів лише один раз
    if not launcher_message_sent:
        client.send("server", "list_clients")

    # Зменшена пауза для отримання повідомлення від серверу
    time.sleep(0.5)

    # Отримуємо повідомлення
    messages = client.received_messages

    for msg in messages:
        message_counter += 1

        # Ігноруємо тільки перше повідомлення
        if message_counter == 1:
            print(f"Ігноруємо повідомлення #{message_counter}: {msg}")
            continue

        # Якщо кілька повідомлень прийшли разом, розділимо їх
        split_messages = msg.split('}{')  # Розділяємо на частини за "{"

        # Додаємо фігурні дужки назад до кожного повідомлення
        split_messages = [split_messages[0]] + ['{' + m + '}' for m in split_messages[1:]]

        for part in split_messages:
            try:
                # Перетворюємо кожну частину на словник
                data = json.loads(part)

                # Перевіряємо, чи це відповідь від серверу
                if data.get("from") == "server" and data.get("command") == "list_clients":
                    clients = data.get("clients", [])
                    print(f"Підключені клієнти: {clients}")
                    
                    # Перевіряємо, чи є клієнт "launcher" і надсилаємо тільки один раз
                    if "launcher" in clients and not launcher_message_sent:
                        print("Клієнт 'launcher' знайдений, надсилаємо повідомлення...")
                        client.send("launcher", "show_window")
                        launcher_message_sent = True  # Відзначаємо, що повідомлення вже надіслано
                    elif "launcher" not in clients:
                        print("Клієнт 'launcher' не знайдений.")
                
            except json.JSONDecodeError:
                print("Неможливо розпізнати повідомлення або воно пошкоджене:", part)

if __name__ == "__main__":
    client.start()

    while not launcher_message_sent:
        check_for_launcher()
