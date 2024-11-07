import json
import os
import subprocess
import time
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from tkinter import Menu
from tkinter import colorchooser
import logging
from logging.handlers import RotatingFileHandler
import psutil
from pystray import Icon, Menu as TrayMenu, MenuItem as TrayMenuItem
from PIL import Image, ImageDraw, ImageGrab, ImageTk
import threading
from datetime import datetime
import ctypes
import sys
from UniClient import Client
import keyboard
print("all import done")

class AppLauncher:
    def __init__(self, root):
        self.root = root
        self.dev_mode = False
        self.kernel32 = ctypes.windll.kernel32
        self.user32 = ctypes.windll.user32
        self.console_window = self.kernel32.GetConsoleWindow()
        self.disable_console_close_button()
        self.color_code = "#FFFFFF"
        self.hidden_mode = False
        self.client_name = "launcher"
        self.attributes = {}
        self.load_config()
        self.hide_console_with_start()
        print("config load")
        self.log_file = "launcher.log"
        self.programs = {}
        self.processes = {}
        self.start_times = {}
        self.setup_logging()
        #self.create_interface()
        
        
        self.main_frame = tk.Frame(self.root, bg=self.color_code)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.mainFrame = 'MAIN'
        self.create_interface(self.main_frame)
        
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.load_programs_and_refresh()
        self.load_running_programs()
        tray_thread = threading.Thread(target=self.run_in_tray, daemon=True)
        tray_thread.start()
        print("tray thread start")
        self.keyboard_thread = None
        self.flag_new_console = False
        

        self.with_start_update_background(self.color_code)
        self.root.after(5000, self.check_autorestart)
        # Інтеграція з TeServer
        self.client = Client(name=self.client_name, server_host="localhost", server_port=65432)
        print("client start")


        # Запускаємо окремий потік для обробки повідомлень від інших клієнтів
        self.receive_thread = threading.Thread(target=self.client.receive_messages)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        print("start receive_messages")
        
        #self.check_for_messages()
        self.root.after(500, self.check_for_messages)
        
        self.connect = threading.Thread(target=self.client.start)
        self.connect.daemon = True
        self.connect.start()
        
        self.registered_hotkeys = set()
        self.start_keyboard_listener()
        print("keyboard listener start")

        self.console_thread = threading.Thread(target=self.console)
        self.console_thread.daemon = True  # Потік завершиться разом із програмою
        self.console_thread.start()
        print("console thread start")
    
    def program_list(self):
        program_names = list(self.programs.keys())
        print("Program list:")
        for name in program_names:
            print(name)
    
    def update_interface(self):
        self.create_empty_frame(self.main_frame)
        self.mainFrame = 'empty'
    
    def back_update_interface(self):
        self.create_interface(self.main_frame)
        self.mainFrame = 'MAIN'
    
        
        
        
    def update_variable(self, *args):
        if len(args) < 2:
            print("Помилка: не вказано нове значення для змінної.")
            return

        var_name = args[0]  # Назва змінної
        new_value = args[-1]  # Останній аргумент - нове значення

        if hasattr(self, var_name):
            attr = getattr(self, var_name)
            # Якщо вказано індекс і атрибут є списком
            if len(args) == 3 and isinstance(args[1], int) and isinstance(attr, list):
                index = args[1]
                try:
                    attr[index] = new_value
                    print(f"Значення '{var_name}[{index}]' змінено на {new_value}")
                except IndexError:
                    print(f"Помилка: індекс {index} виходить за межі списку '{var_name}'.")
            # Якщо індекс не вказано
            elif len(args) == 2:
                setattr(self, var_name, new_value)
                print(f"Значення '{var_name}' змінено на {new_value}")
            else:
                print("Помилка: неправильний формат аргументів.")
        else:
            print(f"Змінної '{var_name}' не знайдено.")
    
    
    def get_variable(self, *args):
        if len(args) < 1:
            print("Помилка: не вказано назву змінної для виведення.")
            return

        var_name = args[0]  # Назва змінної

        if hasattr(self, var_name):
            attr = getattr(self, var_name)
            # Якщо змінна є списком і вказано індекс
            if len(args) == 2 and isinstance(args[1], int) and isinstance(attr, list):
                index = args[1]
                try:
                    print(f"Значення '{var_name}[{index}]' = {attr[index]}")
                except IndexError:
                    print(f"Помилка: індекс {index} виходить за межі списку '{var_name}'.")
            # Якщо індекс не вказано
            elif len(args) == 1:
                print(f"Значення '{var_name}' = {attr}")
            else:
                print("Помилка: неправильний формат аргументів.")
        else:
            print(f"Змінної '{var_name}' не знайдено.")
            
    def list_variables(self):
        attributes = vars(self)  # Отримуємо всі атрибути об'єкта як словник
        for name, value in attributes.items():
            print(f"{name} = {value}")
    
    
    def load_scripts(self):
        scripts_dir = os.path.join(os.getcwd(), 'scripts')
        if scripts_dir not in sys.path:
            sys.path.append(scripts_dir)
            
    
    
    def execute_script(self, *args):
        # Перевіряємо, чи є достатньо аргументів
        if len(args) < 1:
            print("Помилка: не вказано файл для виконання.")
            return
        
        script_name = args[0]  # Назва файлу для виконання
        script_args = args[1:]  # Додаткові аргументи

        # Перевіряємо, чи існує файл
        script_path = os.path.join(os.getcwd(), 'scripts', script_name)
        if not os.path.exists(script_path):
            print(f"Скрипт '{script_name}' не знайдено в папці 'scripts'.")
            return
        
        # Виконуємо файл і передаємо додаткові аргументи
        try:
            with open(script_path, 'r', encoding='utf-8') as file:
                script_code = file.read()
                exec(script_code, {"__name__": "__main__", "args": script_args, "app": self})
            #print(script_name)
        except Exception as e:
            print(f"Помилка при виконанні скрипту '{script_name}': {e}")
    
    
    
    
    def selected_program(self):
        if self.mainFrame == 'MAIN':
            self.selectedraw = self.listbox.curselection()
            #print(self.selectedraw)
            if self.selectedraw:  # Перевірити, чи є обрані елементи
                listbox_entry = self.listbox.get(self.selectedraw[0])  # Отримати елемент за першим індексом
                #print(listbox_entry)
                self.selected_program_name = listbox_entry.split(" (")[0]
                #print(self.selected_program_name)
        else:
            print('')

    def start_program_console(self):
        self.launch_program(self.selected_program_name)
    
    def displays_client_name(self):
        print(self.client_name)
    
    def help_list(self):
        """Виводить список команд і гарячих клавіш у консоль з описами з файлу налаштувань."""
        print("\nCommands:")
        for command, description in self.descriptions.get("commands", {}).items():
            print(f"{command} - {description}")

        print("\nHot keys:")
        for hotkey, description in self.descriptions.get("hotkeys", {}).items():
            print(f"{hotkey} - {description}")
        print("")
    
    def disconnect_server(self):
        self.client.close()
    
    def restart_keyListener_thread(self):
        self.stop_keyboard_listener()
        self.startKeyListen()
    
    def start_keyboard_listener(self):
        # Якщо потік уже запущений, зупиняємо його перед запуском нового
        if self.use_hotkey == True:
            if self.keyboard_thread and self.keyboard_thread.is_alive():
                self.stop_keyboard_listener()
    
            self.key_thread_running = True
            self.keyboard_thread = threading.Thread(target=self.listen_for_hotkeys, daemon=True)
            self.keyboard_thread.start()
        
    def startKeyListen(self):
        self.key_thread_running =True
        self.start_keyboard_listener()
    
    def stop_keyboard_listener(self):
        # Зупиняємо потік
        self.key_thread_running = False
        if self.keyboard_thread:
            self.keyboard_thread.join()  # Чекаємо, поки потік завершиться
        # Видаляємо зареєстровані гарячі клавіші
        for hotkey in self.registered_hotkeys:
            keyboard.remove_hotkey(hotkey)
        self.registered_hotkeys.clear()

    def listen_for_hotkeys(self):
        """Цикл прослуховування гарячих клавіш з регулярним оновленням."""
        while self.key_thread_running:
            # print(self.key_thread_running)
            try:
                # Перереєструємо гарячі клавіші кожні 5 секунд
                for hotkey, action in self.hotkeys.items():
                    # Видаляємо гарячі клавіші, якщо вони вже зареєстровані
                    if hotkey in self.registered_hotkeys:
                        keyboard.remove_hotkey(hotkey)
    
                    # Додаємо гарячу клавішу заново
                    keyboard.add_hotkey(hotkey, action)
                    self.registered_hotkeys.add(hotkey)
    
                # Затримка для повторної перереєстрації
                time.sleep(5)
    
            except Exception as e:
                print(f"Помилка: {e}")
                # Видаляємо всі зареєстровані гарячі клавіші та очищуємо список
                for hotkey in list(self.registered_hotkeys):
                    keyboard.remove_hotkey(hotkey)
                self.registered_hotkeys.clear()
                time.sleep(5)  # Затримка перед повторною спробою

    

    def recconect(self):
        self.client.restart_connection()
        
    def check_for_messages(self):
        """Перевіряє наявність нових повідомлень кожні 500 мс."""
        if self.client.received_messages:
            message = self.client.received_messages.pop(0)
            if self.print_receive_message:
                print(message)
            self.process_client_message(message)

        # Викликаємо цю ж функцію знову через 500 мс
        self.root.after(500, self.check_for_messages)
    
    def send_message(self, *args):


        # Перевіряємо, чи достатньо аргументів для команди
        if len(args) >= 2:
            target_name = args[0]  # Ім'я клієнта
            message = " ".join(args[1:])  # Все, що після першого аргументу - це повідомлення
    
            try:
                self.client.send(target_name, message)
                print(f"Message send client {target_name}: {message}")
            except Exception as e:
                print(f"Error with sending message: {e}")
        else:
            print("Error command. Use: send <client name> <message>")
        
    def process_client_message(self, message):
        """Обробляє отримані від клієнтів повідомлення."""
        try:
            # Парсимо повідомлення як JSON
            message_data = json.loads(message)

            # Перевіряємо, чи є в повідомленні необхідні поля
            if "from" in message_data and "message" in message_data:
                sender = message_data["from"]
                content = message_data["message"]
                if self.notify_with_client_msg:
                    print(f"Message received from {sender}: {content}")

                # Перевіряємо, чи повідомлення містить "command=None"
                if "command=None" in content:
                    # Видаляємо "command=None" з тексту повідомлення
                    content = content.replace("command=None,", "").strip()
                    # Пропускаємо обробку команди для ланчера
                    print(f"Filtered message from {sender}: {content}")
                else:
                    if self.execute_command_with_client == True:
                        # Обробляємо команду, якщо це команда для ланчера
                        self.handle_launcher_command(sender, content)
                    else:
                        return

        except json.JSONDecodeError:
            print("Failed to parse JSON message")

    def handle_launcher_command(self, sender, command):
        if self.use_black_list:
            if sender in self.banned:
                print(f'{sender} in black list')
            else:
                # Розбиваємо command на перше слово (команду) і решту слів (аргументи)
                args = command.split()
                cmd_name = args[0]
                cmd_args = args[1:]

                if cmd_name in self.commands:
                    if self.notify_with_client_msg:
                        print(f"Execution of the command from {sender}: {cmd_name}")
                    # Викликаємо команду з аргументами
                    self.commands[cmd_name](*cmd_args)
                else:
                    print(f"Unknown command: {cmd_name}")

        elif self.use_white_list:
            if sender in self.white_list:
                # Розбиваємо command на команду і аргументи
                args = command.split()
                cmd_name = args[0]
                cmd_args = args[1:]

                if cmd_name in self.commands:
                    if self.notify_with_client_msg:
                        print(f"Execution of the command from {sender}: {cmd_name}")
                    self.commands[cmd_name](*cmd_args)
                else:
                    print(f"Unknown command: {cmd_name}")
            else:
                return
        else:
            # Розбиваємо command на команду і аргументи
            args = command.split()
            cmd_name = args[0]
            cmd_args = args[1:]

            if cmd_name in self.commands:
                if self.notify_with_client_msg:
                    print(f"Execution of the command from {sender}: {cmd_name}")
                self.commands[cmd_name](*cmd_args)
            else:
                print(f"Unknown command: {cmd_name}")
                
                
    def exec_command(self, *args):
    # Решта аргументів об'єднуємо в один рядок для виконання як коду
        code_to_execute = " ".join(args[0:])
        
        try:
            # Виконуємо переданий код
            exec(code_to_execute)
            print(code_to_execute)
            print(code_to_execute)
        except Exception as e:
            print(f"Error executing code: {e}")


    def console(self):
        while self.console_work:
            command = input(">").strip()  # Отримуємо команду
            if command:
                args = command.split()  # Розділяємо команду і аргументи
                args[0] = args[0].lower()
                if len(args) > 0:  # Перевіряємо, чи є в команді аргументи
                    if args[0] == "exit":
                        self.exit_app_from_menu()
                        break
                    elif args[0] in self.commands:
                        self.root.after(0, self.commands[args[0]], *args[1:])  # Виконуємо команду з аргументами
                    else:
                        if self.if_not_command:
                            try:
                                subprocess.run(command, shell=True)
                            except Exception as e:
                                print(f"An error occurred while executing the command: {e}")
                        else:
                            print(f"Unknown command: {args[0]}")
            else:
                print(">")
                
                
    def clear_console(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def run_external_program(self, *args):
        # Перевіряємо, чи є аргумент (шлях до програми)
        if len(args) > 0:
            path = " ".join(args)  # Об'єднуємо всі аргументи в один рядок, обробляючи пробіли
            try:
                subprocess.Popen(path, shell=True)
                print(f"Secsesful {path} run.")
            except FileNotFoundError:
                print(f"Not found {path}.")
            except Exception as e:
                print(f"ERROR: {e}")
        else:
            print("The path to the program is not specified.")
    
    
    def show_program_info(self, *args):
        # Тут ми використовуємо *args для прийняття всіх аргументів
        if len(args) > 0:
            program_name = " ".join(args)
            if program_name in self.processes:
                pids = self.processes[program_name]
                print(f"Information about the program: {pids}, {self.program_details}")
        else:
            print("The name of the program is not specified.")
    
    def list_running_programs(self):
        if self.processes:
            for program_name, pids in self.processes.items():
                print(f"{program_name}: {pids}")
        else:
            print("Not started program.")

    def clear_running_programs(self):
        # Очищуємо файл running_programs.json
        try:
            with open('running_programs.json', 'w', encoding='utf-8') as file:
                json.dump({}, file, indent=4, ensure_ascii=False)  # Записуємо порожній об'єкт
            self.logger.info("File running_programs.json clear.")
            messagebox.showinfo("Success", "Файл running_programs.json seccess clearead.")
        except Exception as e:
            self.logger.error(f"Error clearing running_programs.json file: {e}")
            messagebox.showerror("Error", f"Failed to clear file: {e}")

    
    def freeze_program(self):
        if self.mainFrame == 'MAIN':
            selected = self.listbox.curselection()
            if selected:
                listbox_entry = self.listbox.get(selected)
                program_name = listbox_entry.split(" (")[0]
                if program_name in self.processes and self.processes[program_name]:
                    for pid in self.processes[program_name]:
                        try:
                            process = psutil.Process(pid)
                            process.suspend()  # Заморозка процесу
                            self.update_status(program_name, "Frezed")
                            self.logger.info(f"Program '{program_name}' frozen (PID: {pid})")
                        except psutil.NoSuchProcess:
                            self.logger.error(f"Failed to freeze the program '{program_name}' (PID: {pid}) - process not found.")
            else:
                print('')
    
    def load_running_programs(self):
        if os.path.exists('running_programs.json'):
            with open('running_programs.json', 'r', encoding='utf-8') as file:
                running_programs = json.load(file)
                for name, info in running_programs.items():
                    # Перевірка наявності PID
                    if info['pid'] and psutil.pid_exists(info['pid'][0]):  # Якщо список PID не порожній і процес існує
                        self.processes[name] = info['pid']
                        self.update_status(name, "Запущено")
                    else:
                        self.logger.info(f"Program '{name}' is not running or has no active ones PID.")
    
    
    
    def save_running_programs(self):
        running_programs = {name: {"pid": pids} for name, pids in self.processes.items()}
        with open('running_programs.json', 'w', encoding='utf-8') as file:
            json.dump(running_programs, file, indent=4, ensure_ascii=False)
    

    def check_autorestart(self):
        for program_name, pids in self.processes.items():
            if "autorestart" in self.programs[program_name].get("attributes", []):
                for pid in pids:
                    if not psutil.pid_exists(pid):
                        self.logger.info(f"Program '{program_name}' was closed from outside, restart...")
                        self.launch_program(program_name)

        self.root.after(5000, self.check_autorestart)




    def toggle_hidden_programs(self):
        self.hidden_mode = not self.hidden_mode
        self.refresh_program_list()
    
    def hide_console_with_start(self):
        if self.dev_mode == False:
            console_window = self.kernel32.GetConsoleWindow()
            if console_window != 0:
                self.user32.ShowWindow(console_window, 0)  # 0 - приховати\
        return
    
    def hide_console(self):
        console_window = self.kernel32.GetConsoleWindow()
        if console_window != 0:
            self.user32.ShowWindow(console_window, 0)  # 0 - приховати\
            
    def show_console(self):
        console_window = self.kernel32.GetConsoleWindow()
        if console_window != 0:
            self.user32.ShowWindow(console_window, 5)  # 5 - показати
    
    def toggle_console_visibility(self):
        if self.console_window != 0:
            # Отримуємо поточний стан консолі
            is_visible = self.user32.IsWindowVisible(self.console_window)
            if is_visible:
                self.hide_console()  # Якщо консоль видима, приховуємо її
            else:
                self.show_console()  # Якщо консоль прихована, показуємо її
    
    
    
    def disable_console_close_button(self):
        """Заборонити закриття вікна консолі через кнопку 'X'"""
        if self.console_window:
            GWL_STYLE = -16  # Стиль вікна
            WS_SYSMENU = 0x80000  # Стиль системного меню

            style = self.user32.GetWindowLongA(self.console_window, GWL_STYLE)
            style &= ~WS_SYSMENU  # Видалити можливість закриття вікна
            self.user32.SetWindowLongA(self.console_window, GWL_STYLE, style)
    
    def load_config(self):
        """Завантажує конфігурацію з файлу config.json."""
        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as file:
                config = json.load(file)
                self.programs_file = config.get('programs_file', 'programs.json')
                self.color_code = config.get('color', '#FFFFFF')
                self.attributes = config.get('attributes', {})
                self.dev_mode = config.get('dev', 'False').lower() == 'true'
                self.client_name = config.get('client_name', 'launcher')
                self.if_not_command = config.get('if_not_command', 'True').lower() == 'true'
                self.use_hotkey = config.get('use_hotkey', 'True').lower() == 'true'
                self.console_work = config.get('console_work', 'True').lower() == 'true'
                self.notify_with_client_msg = config.get('notify_with_client_msg', 'True').lower() == 'true'
                self.print_receive_message = config.get('print_receive_message', 'True').lower() == 'true'
                self.use_black_list = config.get('use_black_list', 'False').lower() == 'true'
                self.use_white_list = config.get('use_white_list', 'False').lower() == 'true'
                self.execute_command_with_client = config.get('execute_command_with_client', 'True').lower() == 'true'
                self.banned = config.get('banned', '')
                self.white_list = config.get('white_list', '')
                
                self.hotkeys = {key: getattr(self, func, None) for key, func in config.get('hotkeys', {}).items()}
                self.commands = {cmd: getattr(self, func, None) for cmd, func in config.get('commands', {}).items()}
                self.descriptions = config.get('descriptions', {})


    def setup_logging(self):
        self.logger = logging.getLogger("AppLauncher")
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(self.log_file, maxBytes=1000000, backupCount=3)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def add_program(self):
        program_name = simpledialog.askstring("Program name", "Enter the name of the program:")
        if program_name:
            program_path = filedialog.askopenfilename(title="Select a program")
            if program_path:
                attributes = simpledialog.askstring("Attributes", "Enter attributes separated by commas (sys, autorun, test):")
                self.programs[program_name] = {
                    "path": program_path,
                    "command": program_path,
                    "close_command": "",
                    "launch_count": 0,
                    "total_runtime": 0.0,
                    "description": "",
                    "self_console": "False",
                    "attributes": [attr.strip() for attr in attributes.split(',')] if attributes else []
                }
                self.save_programs()
                self.refresh_program_list()
                
    def apply_attributes(self, program_info):
        for attribute in program_info.get("attributes", []):
            action = self.attributes.get(attribute)
            if action:
                if action.startswith("file:"):
                    file_command = action.split("file:", 1)[1].strip()
                    subprocess.Popen(file_command, shell=True)
                elif action.startswith("command:"):
                    command = action.split("command:", 1)[1].strip()
                    subprocess.Popen(command, shell=True)
                elif action.startswith("def:"):
                    func_name = action.split("def:", 1)[1].strip()
                    getattr(self, func_name, lambda: None)()
    

    
    def launch_program(self, program_name=None):
        if not program_name:
            if self.mainFrame == 'MAIN':
                selected = self.listbox.curselection()
                if selected:
                    listbox_entry = self.listbox.get(selected)
                    program_name = listbox_entry.split(" (")[0]
            else:
                print('')

        if program_name:
            program_info = self.programs.get(program_name)
            if not program_info:
                return

            self.apply_attributes(program_info)
            
            try:
                self.flag_new_console = (program_info["self_console"]).lower() == 'true'
            except Exception as e:
                self.flag_new_console = False
            
            command = program_info["command"]
            program_dir = os.path.dirname(program_info["path"])
            
            try:
                if self.flag_new_console:
                    process = subprocess.Popen(command, cwd=program_dir, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    process = subprocess.Popen(command, cwd=program_dir, shell=True)
                pid = process.pid
                if program_name not in self.processes:
                    self.processes[program_name] = []
                self.processes[program_name].append(pid)
                self.start_times[pid] = time.time()
                self.programs[program_name]["launch_count"] += 1
                self.update_status(program_name, "Запущено")
                self.logger.info(f"Program '{program_name}' launched with the command: {command}")
                self.save_programs()
                self.save_running_programs()
            except Exception as e:
                self.update_status(program_name, f"Помилка: {e}")
                self.logger.error(f"Failed to launch the program '{program_name}': {e}")

    def launch_program_manager(self):
        """Запуск вказаної програми"""
        program_path = "ProgramManager.py"
        try:
            subprocess.Popen([program_path], shell=True)
            print(f"Program {program_path} seccess run.")
        except FileNotFoundError:
            print(f"Error: program {program_path} not found.")
        except Exception as e:
            print(f"An error occurred while starting the program: {e}")
    

    
    def update_program_list_with_search(self, event):
        if self.mainFrame == 'MAIN':
            search_term = self.search_var.get().lower()
            filtered_programs = {}

            # Фільтрувати програми на основі режиму відображення (приховані/неприховані)
            for name, info in self.programs.items():
                if search_term in name.lower():
                    if self.hidden_mode and "hide" not in info.get("attributes", []):
                        continue  # Ігноруємо неприховані програми в режимі прихованих
                    elif not self.hidden_mode and "hide" in info.get("attributes", []):
                        continue  # Ігноруємо приховані програми в режимі звичайних
                    filtered_programs[name] = info

            self.refresh_program_list(filtered_programs)
        else:
            print('')
    
    def close_program(self):
        if self.mainFrame == 'MAIN':
            selected = self.listbox.curselection()
            if selected:
                listbox_entry = self.listbox.get(selected)
                program_name = listbox_entry.split(" (")[0]
                if program_name in self.processes and self.processes[program_name]:
                    for pid in self.processes[program_name]:
                        self.terminate_process_tree(pid)
                        start_time = self.start_times.pop(pid, None)
                        if start_time:
                            elapsed_time = time.time() - start_time
                            self.programs[program_name]["total_runtime"] += elapsed_time
                            self.logger.info(f"Program '{program_name}' (PID: {pid}) completed through {elapsed_time:.2f} second")
                    self.processes[program_name] = []
                    self.update_status(program_name, "Зупинено")
                    self.save_programs()
                    self.save_running_programs()

                # Перевірка на наявність атрибута 'refresh'
                    if "refresh" in self.programs[program_name].get("attributes", []):
                        self.logger.info(f"Reload 'programs.json' after completing the program '{program_name}'")
                        self.load_programs_and_refresh()

                else:
                    self.update_status(program_name, "Не запущено")
                    self.logger.info(f"Attempting to end the program '{program_name}', which was not launched")
        else:
            print('')


    def terminate_process_tree(self, pid):
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            psutil.wait_procs(children, timeout=5)
            parent.terminate()
            parent.wait(5)
        except psutil.NoSuchProcess:
            pass

    def save_programs(self):
        with open(self.programs_file, 'w', encoding='utf-8') as file:
            json.dump(self.programs, file, indent=4, ensure_ascii=False)

    def load_programs(self):
        if os.path.exists(self.programs_file):
            with open(self.programs_file, 'r', encoding='utf-8') as file:
                self.programs = json.load(file)
                
        self.refresh_program_list()

    def load_programs_and_refresh(self):
        if self.mainFrame == 'MAIN':
            self.load_programs()
            for program_name, program_info in self.programs.items():
                if "autorun" in program_info.get("attributes", []):
                    self.launch_program(program_name)
            self.check_programs_status()
        else:
            print("функція працює тільки в головному фреймі")

    def refresh_program_list(self, programs=None):
        self.listbox.delete(0, tk.END)
        programs = programs or self.programs

        for program_name, program_info in programs.items():
            if self.hidden_mode:
                if "hide" not in program_info.get("attributes", []):
                    continue
            else:
                if "hide" in program_info.get("attributes", []):
                    continue

            status = "Запущено" if self.processes.get(program_name) else "Зупинено"
            color = "green" if status == "Запущено" else "black"
            self.listbox.insert(tk.END, f"{program_name} ({status})")
            if self.listbox.size() > 0:
                self.listbox.itemconfig(tk.END, fg=color)

    
    def open_file_location(self):
        selected = self.listbox.curselection()
        if selected:
            listbox_entry = self.listbox.get(selected)
            program_name = listbox_entry.split(" (")[0]
            program_info = self.programs.get(program_name)
            if program_info:
                file_path = program_info.get("path")
                if file_path and os.path.exists(file_path):
                    folder_path = os.path.dirname(file_path)
                    os.startfile(folder_path)
                else:
                    messagebox.showerror("Error", "File not found.")


    def update_status(self, program_name, status):
        for index in range(self.listbox.size()):
            listbox_entry = self.listbox.get(index)
            if listbox_entry.startswith(program_name):
                color = "green" if status == "Запущено" else "black"
                self.listbox.delete(index)
                self.listbox.insert(index, f"{program_name} ({status})")
                self.listbox.itemconfig(index, fg=color)
                break

    def show_program_details(self, event):
        self.selected_program()
        selected = self.listbox.curselection()
        if selected:
            listbox_entry = self.listbox.get(selected)
            program_name = listbox_entry.split(" (")[0]
            program_info = self.programs.get(program_name, {})

            if not program_info:
                details = "No program information found."
            else:
                total_runtime = program_info.get("total_runtime", 0.0)
                hours = int(total_runtime // 3600)  # Повні години
                minutes = int((total_runtime % 3600) // 60)  # Повні хвилини

                details = (
                    f"Назва: {program_name}\n"
                    f"Шлях: {program_info.get('path', '')}\n"
                    f"Кількість запусків: {program_info.get('launch_count', 0)}\n"
                    f"Загальний час роботи: {hours} годин {minutes} хвилин\n"
                    f"Опис: {program_info.get('description', '')}\n"
                )
                self.program_details = details
            self.details_label.config(text=details)
        else:
            self.details_label.config(text="Виберіть програму для перегляду деталей.")

    def edit_program(self):
        selected = self.listbox.curselection()
        if selected:
            listbox_entry = self.listbox.get(selected)
            program_name = listbox_entry.split(" (")[0]

            new_name = simpledialog.askstring("Редагувати програму", "Введіть нову назву програми:", initialvalue=program_name)
            new_path = filedialog.askopenfilename(title="Виберіть новий шлях до програми")

            if new_name and new_path:
                self.programs[new_name] = {
                    **self.programs.pop(program_name),
                    "path": new_path
                }
                self.save_programs()
                self.refresh_program_list()
    
    def hide_window(self):
        self.root.withdraw()
        
    def show_window(self):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
            
    def toggle_visibility_window(self):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
        else:
            self.root.withdraw()
    

    def delete_program(self):
        selected = self.listbox.curselection()
        if selected:
            listbox_entry = self.listbox.get(selected)
            program_name = listbox_entry.split(" (")[0]

        # Перевірка на наявність атрибута 'sys'
            if "sys" in self.programs.get(program_name, {}).get("attributes", []):
                messagebox.showerror("Помилка", f"Програму '{program_name}' не можна видалити, оскільки вона має атрибут 'sys'.")
                return

        # Діалогове вікно підтвердження
            confirm = messagebox.askyesno("Підтвердження видалення", f"Ви впевнені, що хочете видалити програму '{program_name}'?")
            if confirm:
                del self.programs[program_name]
                self.save_programs()
                self.refresh_program_list()

    def check_programs_status(self):
        for program_name, pids in list(self.processes.items()):
            for pid in pids:
                if not psutil.pid_exists(pid):
                    self.processes[program_name].remove(pid)
                    start_time = self.start_times.pop(pid, None)
                    if start_time:
                        elapsed_time = time.time() - start_time
                        self.programs[program_name]["total_runtime"] += elapsed_time
                        self.logger.info(f"Програма '{program_name}' (PID: {pid}) завершена через {elapsed_time:.2f} секунд")
                    self.update_status(program_name, "Зупинено" if not self.processes[program_name] else "Запущено")
        self.root.after(2000, self.check_programs_status)  # Перевірка кожні 2 секунди


    def create_interface(self, frame):
        # Очищення фрейму перед заповненням
        for widget in frame.winfo_children():
            widget.destroy()

        # Конфігурація вікна
        self.root.title("Launcher")
        self.root.geometry("600x400")
        self.root.configure(bg=self.color_code)
        self.create_search_bar(frame)
        # Іконка для вікна
        self.root.iconbitmap('icon.ico')

        # Верхнє меню
        menubar = Menu(self.root)

        # Вкладка "Файл"
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Додати програму", command=self.add_program)
        file_menu.add_command(label="Очистити файл кеш", command=self.clear_running_programs)
        file_menu.add_command(label="Відкрити папку скрипта", command=self.open_script_folder)
        file_menu.add_command(label="Менеджер програм", command=self.launch_program_manager)
        menubar.add_cascade(label="Файл", menu=file_menu)

        # Вкладка "Інтерфейс"
        interface_menu = Menu(menubar, tearoff=0)
        interface_menu.add_command(label="Змінити колір інтерфейсу", command=self.choose_color)
        interface_menu.add_command(label="Зберегти значення кольору", command=self.save_color_to_config)
        interface_menu.add_command(label="Показати приховані програми", command=self.toggle_hidden_programs)
        menubar.add_cascade(label="Інтерфейс", menu=interface_menu)

        # Вкладка "Додаткове"
        extra_menu = Menu(menubar, tearoff=0)
        extra_menu.add_command(label="Перезавантажити список програм", command=self.load_programs_and_refresh)
        extra_menu.add_command(label="Показати/приховати консоль", command=self.toggle_console_visibility)
        extra_menu.add_command(label="Показати/приховати вікно ланчера", command=self.toggle_visibility_window)
        extra_menu.add_command(label="Вийти", command=self.exit_app_from_menu)
        menubar.add_cascade(label="Додаткове", menu=extra_menu)
        
        # Додаємо меню до вікна
        self.root.config(menu=menubar)

        # Пошуковий рядок
        

        # Список програм
        self.listbox = tk.Listbox(frame, bg=self.color_code, fg="black")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-1>", self.on_listbox_double_click)
        self.listbox.bind("<Button-3>", self.show_context_menu)
        self.listbox.bind("<ButtonRelease-1>", self.show_program_details)

        # Скролбар
        scrollbar = tk.Scrollbar(frame, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        # Панель деталей
        self.details_label = tk.Label(frame, bg=self.color_code, fg="black", justify=tk.LEFT, anchor="nw", wraplength=300)
        self.details_label.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)

        # Контекстне меню
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Запустити", command=self.launch_program)
        self.context_menu.add_command(label="Зупинити", command=self.close_program)
        self.context_menu.add_command(label="Заморозити програму", command=self.freeze_program)
        self.context_menu.add_command(label="Редагувати", command=self.edit_program)
        self.context_menu.add_command(label="Видалити", command=self.delete_program)
        self.context_menu.add_command(label="Відкрити розташування файлу", command=self.open_file_location)

        # Оновлення списку програм
        self.refresh_program_list()
        self.check_programs_status()
        
        
    def create_search_bar(self, frame):
        self.search_var = tk.StringVar()
        self.search_bar = tk.Entry(frame, textvariable=self.search_var, bg=self.color_code, fg="black")
        self.search_bar.pack(fill=tk.X, pady=5)  # Додаємо параметр `pady` для відступу зверху
        self.search_bar.bind('<KeyRelease>', self.update_program_list_with_search)
        
        
    # Створюємо функцію для створення порожнього фрейму
    def create_empty_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

        label = tk.Label(frame, text="Порожній інтерфейс", font=("Arial", 16), bg=self.color_code)
        label.pack(pady=20)
        back_button = tk.Button(frame, text="Повернутися до головного інтерфейсу", command=lambda: self.back_update_interface())
        back_button.pack(pady=10)

    
    def choose_color(self):
        # Відкриття діалогу для вибору кольору
        color_code = colorchooser.askcolor(title="Виберіть колір")
        if color_code[1]:  # Якщо колір вибрано
            print(color_code)

            self.update_background(color_code[1])
            self.color_code = color_code[1]

    def save_color_to_config(self, config_file='config.json'):
        print(self.color_code)
        try:
            # Відкриваємо файл з налаштуваннями
            with open(config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)

            # Оновлюємо значення кольору
            config['color'] = self.color_code

            # Записуємо зміни назад у файл
            with open(config_file, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=4)

            print(f"Колір {self.color_code} успішно збережено у файл {config_file}.")

        except FileNotFoundError:
            print(f"Файл {config_file} не знайдено.")
        except json.JSONDecodeError:
            print("Помилка в структурі файлу налаштувань.")
        except Exception as e:
            print(f"Виникла помилка: {e}")

    def update_background(self, color):
        # Оновлення кольору фону головного вікна
        if self.mainFrame == 'MAIN':
            self.root.config(bg=color)
            self.listbox.config(bg=color)
            self.details_label.config(bg=color)
            self.search_bar.config(bg=color)
            self.context_menu.config(bg=color)
            # Видалення верхнього меню, якщо воно існує
            self.root.config(menu=None)
            print("Color change and menubar removal successful")
            print(color)
        else:
            print('')

      
      
    def with_start_update_background(self, color):
        # Оновлення кольору фону головного вікна
        if self.mainFrame == 'MAIN':
            self.root.config(bg=color)
            self.listbox.config(bg=color)
            self.details_label.config(bg=color)
            self.search_bar.config(bg=color)
            self.context_menu.config(bg=color)
            # Видалення верхнього меню, якщо воно існує
            self.root.config(menu=None)
            print("Color change and menubar removal successful")
            print(color)
        else:
            print('')
        

    def open_script_folder(self):
    # Отримуємо шлях до папки, з якої запущено скрипт
        if getattr(sys, 'frozen', False):
        # Якщо програма була запакована, використовуємо sys.executable
            program_folder = os.path.dirname(sys.executable)
        else:
        # Якщо це звичайний скрипт, використовуємо __file__
            program_folder = os.path.dirname(os.path.abspath(__file__))
    # Відкриваємо папку в провіднику (для Windows)
        subprocess.Popen(f'explorer "{program_folder}"')

    def exit_app_from_menu(self):
        # Вихід з програми через меню
        self.client.close()
        self.root.quit()

    def create_image(self):
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (width // 4, height // 4, width * 3 // 4, height * 3 // 4),
            fill=(0, 0, 0))
        return image


    def toggle_visibility(self, icon, item):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
        else:
            self.root.withdraw()

    def run_in_tray(self):
    # Створюємо спрощене меню трея
        menu = TrayMenu(
            TrayMenuItem('Launcher', self.toggle_visibility),
            TrayMenu.SEPARATOR, 
            TrayMenuItem('Konsole', self.toggle_console_visibility),
            TrayMenu.SEPARATOR,  # Розділювач
            TrayMenuItem('Exit', self.exit_app)  # Кнопка для виходу з програми
        )
        self.icon = Icon("AppLauncher", self.create_image(), "AppLauncher", menu)
    
        self.icon.run()



    def exit_app(self, icon, item):
        self.client.close()
        icon.stop()
        self.root.quit()

    def show_context_menu(self, event):
            try:
                self.listbox.select_set(self.listbox.nearest(event.y))
                self.context_menu.post(event.x_root, event.y_root)
            except Exception as e:
                self.logger.error(f"Не вдалося відкрити контекстне меню: {e}")

    def on_listbox_double_click(self, event):
            selected = self.listbox.curselection()
            if selected:
                listbox_entry = self.listbox.get(selected)
                program_name = listbox_entry.split(" (")[0]
                self.launch_program(program_name)
            
            
    def take_screenshot(self):
        try:
        
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            screenshot_path = os.path.join(os.getcwd(), f'screenshot_{timestamp}.png')

        
            screenshot = ImageGrab.grab()
            screenshot.save(screenshot_path)

        
            subprocess.Popen(['mspaint', screenshot_path], creationflags=subprocess.CREATE_NO_WINDOW)

        except Exception as e:
            print(f"Виникла помилка: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AppLauncher(root)
    root.mainloop()
