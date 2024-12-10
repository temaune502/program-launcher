import json
import os
import sys
import ctypes
from ctypes import wintypes
import subprocess
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
from tkinter import Menu
from tkinter import colorchooser
import logging
from logging.handlers import RotatingFileHandler
import psutil
from pystray import Icon, Menu as TrayMenu, MenuItem as TrayMenuItem
from PIL import Image, ImageDraw, ImageGrab
import keyboard
import shlex
from UniClient import Client
from locales import Localization
from SystemMonitor import SystemMonitor
print("All import done")

class AppLauncher:
    def __init__(self, root):
        self.root = root
        self.dev_mode = False
        self.kernel32 = ctypes.windll.kernel32
        self.user32 = ctypes.windll.user32
        self.console_window = self.kernel32.GetConsoleWindow()
        self.color_code = "#FFFFFF"
        self.text_color = "#FFFFFF"
        self.hidden_mode = False
        self.client_name = "launcher"
        self.config_file = "config.json"
        self.attributes = {}
        self.categories = [""]
        self.filter_attribute = "NoneAtr"
        self.status_colors = {}
        self.load_config()
        if not self.dev_mode:
            self.disable_console_close_button()
        self.hide_console_with_start()
        self.loc = Localization(locale=self.lang)
        self.loc.set_locale(locale=self.lang)
        print(self.loc._("config_load"))
        self.log_file = "launcher.log"
        self.programs = {}
        self.processes = {}
        self.start_times = {}
        self.setup_logging()

        self.icon = None
        self.search_bar= None
        self.search_var = None
        self.program_details = None
        self.key_thread_running = None
        self.selectedraw = None
        self.selected_program_name = None
        
        #self.create_interface()
        self.main_frame = tk.Frame(self.root, bg=self.color_code)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.mainFrame = 'MAIN'
        self.create_interface(self.main_frame)
        
        self.populate_category_menu()
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.load_programs_and_refresh()
        self.load_running_programs()
        tray_thread = threading.Thread(target=self.run_in_tray, daemon=True)
        tray_thread.start()
        print(self.loc._("tray_thread_start"))
        self.keyboard_thread = None
        self.flag_new_console = False

        self.monitor = SystemMonitor(update_interval=0.2)  # Оновлення кожні 200 мс
        self.monitor.start()

        self.with_start_update_background(self.color_code)
        self.root.after(5000, self.check_autorestart)
        # Інтеграція з TeServer
        if self.TeServerIntegration:
            self.client = Client(name=self.client_name, server_host="localhost", server_port=65432)
            self.client.set_client_notify(self.client_notify)
            print(self.loc._("client_start"))
        # Запускаємо окремий потік для обробки повідомлень від інших клієнтів
            self.receive_thread = threading.Thread(target=self.client.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            print(self.loc._("start_receive_messages"))
        #self.check_for_messages()
            self.root.after(500, self.check_for_messages)
        
            self.connect = threading.Thread(target=self.client.start)
            self.connect.daemon = True
            self.connect.start()
        
        self.registered_hotkeys = set()
        self.start_keyboard_listener()
        print(self.loc._("keyboard_listener_statr"))

        self.console_thread = threading.Thread(target=self.console)
        self.console_thread.daemon = True  # Потік завершиconsole_thread_startться разом із програмою
        self.console_thread.start()
        print(self.loc._("console_thread_start"))
        
        check_executable_thread = threading.Thread(target=self.check_executables, daemon=True)
        check_executable_thread.start()

    def populate_category_menu(self):
        """Динамічне заповнення меню категорій"""
        for category in self.categories:
            self.category_menu.add_command(
                label=category,
                command=lambda cat=category: self.update_category(cat)
            )

    def update_category(self, category):
        """Оновлення поточної категорії та оновлення списку програм"""
        self.filter_attribute = category
        self.refresh_program_list()
        self.load_running_programs()
        
    def program_list(self):
        program_names = list(self.programs.keys())
        print(self.loc._("programs_consol_func"))
        for name in program_names:
            print(name)

    def update_interface(self):
        self.create_empty_frame(self.main_frame)
        self.mainFrame = 'empty'   
    
    def back_update_interface(self):
        self.create_interface(self.main_frame)
        self.mainFrame = 'MAIN'

    def check_executables(self, first_run=True):
        """
        Перевіряє наявність файлів виконуваних програм і статусів.

        Параметри:
            first_run (bool): Чи викликається ця функція вперше (True за замовчуванням).
        """
        if not self.programs:
            if first_run:
                print(self.loc._("program_list_not_load_or_empty"))
            return

        missing_programs = []
        updated_programs = []  # Для фіксації програм, статус яких оновлено
        for program_name, program_info in self.programs.items():
            program_path = program_info.get("path")
            current_status = program_info.get("status")

            # Перевірка наявності виконуваного файлу
            if not program_path or not os.path.exists(program_path):
                # Додаємо програму до списку відсутніх
                missing_programs.append(program_name)
                if current_status != "not_found":
                    self.update_status(program_name, status="not_found")
            else:
                # Якщо програма в списку "not_found", але файл існує
                if current_status == "not_found" and program_name not in self.missing_programs:
                    self.update_status(program_name, status="stopped")
                    updated_programs.append(program_name)

        # Якщо це перший запуск, виводимо повідомлення
        if first_run:
            if missing_programs:
                print(self.loc._("missing_executable_file"))
                if self.notify_missing_program:
                    missing_list = "\n".join(missing_programs)
                    messagebox.showerror(
                        self.loc._("missing_executable_file"),
                        self.loc._("missing_executable_file2").format(missing_list=missing_list),
                    )
                self.show_console()
                for program in missing_programs:
                    print(f" - {program}")
            else:
                print(self.loc._("all_executable_file_found"))

        # Лог для оновлених програм
        if updated_programs:
            print(self.loc._("program_status_updated"))
            for program in updated_programs:
                print(f" - {program}: stopped")

        # Оновлення списку відсутніх програм у пам'яті
        self.missing_programs = missing_programs

        # Запланувати повторну перевірку через 6 секунд
        self.root.after(6000, lambda: self.check_executables(first_run=False))


    def change_lang(self, *args):
        if len(args) < 1:
            # Локалізація помилки, якщо не вказано назву змінної
            print(self.loc._("lang_not_specified"))
            return
        else:
            lang = ''.join(args)
            self.loc.set_locale(lang)
        
    def update_variable(self, *args):
        if len(args) < 2:
            # Локалізація помилки, якщо аргументів менше 2
            print(self.loc._("update_variable_error_1"))
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
                    # Локалізація повідомлення про зміну значення в списку
                    message = self.loc._("change_value")
                    print(message.format(var_name=var_name, index=index, new_value=new_value))
                except IndexError:
                    # Локалізація помилки з індексом
                    print(self.loc._("index_out_of_range").format(index=index, var_name=var_name))
            # Якщо індекс не вказано
            elif len(args) == 2:
                setattr(self, var_name, new_value)
                # Локалізація повідомлення про зміну значення
                message = self.loc._("change_value")
                print(message.format(var_name=var_name, new_value=new_value))
            else:
                # Локалізація помилки з неправильним форматом аргументів
                print(self.loc._("update_variable_error_2"))
        else:
            # Локалізація повідомлення, якщо змінну не знайдено
            print(self.loc._("variable_not_found").format(var_name=var_name))


    def get_variable(self, *args):
        if len(args) < 1:
            # Локалізація помилки, якщо не вказано назву змінної
            print(self.loc._("get_variable_error_1"))
            return

        var_name = args[0]  # Назва змінної

        if hasattr(self, var_name):
            attr = getattr(self, var_name)
            # Якщо змінна є списком і вказано індекс
            if len(args) == 2 and isinstance(args[1], int) and isinstance(attr, list):
                index = args[1]
                try:
                    print(self.loc._("get_variable_value").format(var_name=var_name, index=index, value=attr[index]))
                except IndexError:
                    # Локалізація помилки з індексом
                    print(self.loc._("index_out_of_range").format(index=index, var_name=var_name))
            # Якщо індекс не вказано
            elif len(args) == 1:
                print(self.loc._("get_variable_value").format(var_name=var_name, value=attr))
            else:
                # Локалізація помилки з неправильним форматом аргументів
                print(self.loc._("get_variable_error_2"))
        else:
            # Локалізація повідомлення, якщо змінну не знайдено
            print(self.loc._("variable_not_found").format(var_name=var_name))
            
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
            print(self.loc._("file_not_specified"))
            return
        
        script_name = args[0]  # Назва файлу для виконання
        script_args = args[1:]  # Додаткові аргументи

        # Перевіряємо, чи існує файл
        script_path = os.path.join(os.getcwd(), 'scripts', script_name)
        if not os.path.exists(script_path):
            print(self.loc._("script_not_found").format(script_name=script_name))
            return
        
        # Виконуємо файл і передаємо додаткові аргументи
        try:
            with open(script_path, 'r', encoding='utf-8') as file:
                script_code = file.read()
                exec(script_code, {"__name__": "__main__", "args": script_args, "app": self})
        except Exception as e:
            print(self.loc._("execution_error").format(script_name=script_name, error=str(e)))
    
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
                print(f"Error: {e}")
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
                print(self.loc._("message_send").format(target_name=target_name, message=message))
            except Exception as e:
                print(self.loc._("send_message_error").format(error=str(e)))
        else:
            print(self.loc._("send_message_error_command"))
        
    def process_client_message(self, message):
        try:
            # Парсимо повідомлення як JSON
            message_data = json.loads(message)

            # Перевіряємо, чи є в повідомленні необхідні поля
            if "from" in message_data and "message" in message_data:
                sender = message_data["from"]
                content = message_data["message"]
                if self.notify_with_client_msg:
                    print(self.loc._("message_received").format(sender=sender, content=content))

                # Перевіряємо, чи повідомлення містить "command=None"
                if "command=None" in content:
                    # Видаляємо "command=None" з тексту повідомлення
                    content = content.replace("command=None,", "").strip()
                    # Пропускаємо обробку команди для ланчера
                    print(self.loc._("filtered_message").format(sender=sender, content=content))
                else:
                    if self.execute_command_with_client == True:
                        # Обробляємо команду, якщо це команда для ланчера
                        self.handle_launcher_command(sender, content)
                    else:
                        return

        except json.JSONDecodeError:
            print(self.loc._("json_parse_error"))

    def handle_launcher_command(self, sender, command):
        if self.use_black_list:
            if sender in self.banned:
                print(self.loc._("black_list_message").format(sender=sender))
            else:
                # Розбиваємо command на перше слово (команду) і решту слів (аргументи)
                args = command.split()
                cmd_name = args[0]
                cmd_args = args[1:]

                if cmd_name in self.commands:
                    if self.notify_with_client_msg:
                        print(self.loc._("command_execution2").format(sender=sender, cmd_name=cmd_name))
                    # Викликаємо команду з аргументами
                    self.commands[cmd_name](*cmd_args)
                else:
                    print(self.loc._("unknown_command2").format(cmd_name=cmd_name))

        elif self.use_white_list:
            if sender in self.white_list:
                # Розбиваємо command на команду і аргументи
                args = command.split()
                cmd_name = args[0]
                cmd_args = args[1:]

                if cmd_name in self.commands:
                    if self.notify_with_client_msg:
                        print(self.loc._("command_execution").format(sender=sender, cmd_name=cmd_name))
                    self.commands[cmd_name](*cmd_args)
                else:
                    print(self.loc._("unknown_command2").format(cmd_name=cmd_name))
            else:
                return
        else:
            # Розбиваємо command на команду і аргументи
            args = command.split()
            cmd_name = args[0]
            cmd_args = args[1:]

            if cmd_name in self.commands:
                if self.notify_with_client_msg:
                    print(self.loc._("command_execution").format(sender=sender, cmd_name=cmd_name))
                self.commands[cmd_name](*cmd_args)
            else:
                print(self.loc._("unknown_command2").format(cmd_name=cmd_name))
                
                
    def exec_command(self, *args):
        # Об'єднуємо аргументи в один рядок для виконання
        code_to_execute = " ".join(args[0:])
        sys.set_int_max_str_digits(int(1234567890))
        # Функція, що виконується в окремому потоці
        def execute_code():
            try:
                exec(code_to_execute)
            except Exception as e:
                print(f"Error executing code: {e}")

        # Створюємо і запускаємо окремий потік
        exec_thread = threading.Thread(target=execute_code)
        exec_thread.daemon = True
        exec_thread.start()


    def console(self):

        while self.console_work:
            command = input(">").strip()  # Отримуємо команду
            if command:
                args = command.split()  # Розділяємо команду і аргументи
                if self.lower_console_command:
                    args[0] = args[0].lower()
                else:
                    args[0] = args[0]
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
                                print(self.loc._("execution_error").format(error=e))
                        else:
                            print(self.loc._("unknown_command2").format(cmd=args[0]))
                else:
                    print(">")
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
            print(self.loc._("path_not_specified"))
    
    
    def show_program_info(self, *args):
        # Тут ми використовуємо *args для прийняття всіх аргументів
        if len(args) > 0:
            program_name = " ".join(args)
            if program_name in self.processes:
                pids = self.processes[program_name]
                print(self.loc._("program_info").format(pids=pids, program_details=self.program_details))
            else:
                print(self.loc._("program_not_found").format(program_name=program_name))
        else:
            print(self.loc._("program_name_missing"))
    
    def list_running_programs(self):
        if self.processes:
            for program_name, pids in self.processes.items():
                print(f"{program_name}: {pids}")
        else:
            print(self.loc._("program_not_started"))

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


    def get_selected_programs(self):
        """
        Отримує вибрані програми з Listbox.
        :return: Список назв вибраних програм.
        """
        selected = self.listbox.curselection()
        if not selected:
            return []

        # Повертаємо чисті назви програм (без додаткової інформації)
        return [self.listbox.get(i).split(" (")[0] for i in selected]

    def suspend_process(self, pid: int, include_children: bool = True) -> bool:
        """
        Призупиняє процес за вказаним PID і, за потреби, всі його дочірні процеси.
        :param pid: Ідентифікатор процесу (PID).
        :param include_children: Якщо True, також призупиняє всі дочірні процеси.
        :return: True, якщо успішно, False у разі помилки.
        """
        PROCESS_SUSPEND_RESUME = 0x0800
        NTSTATUS = ctypes.c_int

        # Завантажуємо необхідні функції Windows API
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        NtSuspendProcess = ctypes.WINFUNCTYPE(NTSTATUS, wintypes.HANDLE)(
            ("NtSuspendProcess", ctypes.WinDLL("ntdll"))
        )
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        pids_to_suspend = [pid]
        if include_children:
            pids_to_suspend.extend(self.get_child_processes(pid))

        success = True
        for pid_to_suspend in pids_to_suspend:
            process_handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid_to_suspend)
            if not process_handle:
                error_code = ctypes.get_last_error()
                if self.dev_mode:  # Якщо dev_mode увімкнено, виводимо повідомлення
                    print(f"Не вдалося відкрити процес PID {pid_to_suspend}. Код помилки: {error_code}")
                success = False
                continue

            try:
                status = NtSuspendProcess(process_handle)
                if status != 0:
                    if self.dev_mode:
                        print(f"Не вдалося призупинити процес PID {pid_to_suspend}. Код помилки: {status}")
                    success = False
                else:
                    if self.dev_mode:
                        print(f"Процес PID {pid_to_suspend} успішно призупинений.")
            finally:
                kernel32.CloseHandle(process_handle)

        return success

    def get_child_processes(self, pid: int):
        """
        Отримує всіх дочірніх процесів для вказаного PID.
        :param pid: Ідентифікатор батьківського процесу.
        :return: Список PID дочірніх процесів.
        """
        try:
            parent_process = psutil.Process(pid)
            child_processes = parent_process.children(recursive=True)
            return [child.pid for child in child_processes]
        except psutil.NoSuchProcess:
            print(f"Процес PID {pid} не знайдено.")
            return []
    
    def suspend_selected(self):
        """
        Призупиняє вибрані процеси з Listbox.
        """
        selected_programs = self.get_selected_programs()
        if not selected_programs:
            if self.dev_mode:  # Якщо dev_mode увімкнено, виводимо повідомлення
                print("Жодної програми не вибрано для призупинення.")
            return

        for program_name in selected_programs:
            pids = self.processes.get(program_name, [])
            if not pids:
                if self.dev_mode:  # Якщо dev_mode увімкнено, виводимо повідомлення
                    print(f"У програми {program_name} немає активних процесів.")
                continue

            for pid in pids:
                self.update_status(program_name, status = "freez")
                success = self.suspend_process(pid, include_children=True)
                if success:
                    if self.dev_mode:  # Якщо dev_mode увімкнено, виводимо повідомлення
                        print(f"Процес PID {pid} і всі його дочірні процеси для програми {program_name} призупинені.")
                else:
                    if self.dev_mode:  # Якщо dev_mode увімкнено, виводимо повідомлення
                        print(f"Не вдалося призупинити процес PID {pid} для програми {program_name}.")

    def resume_process(self, pid: int, include_children: bool = True) -> bool:
        """
        Розморожує процес за вказаним PID і, за потреби, всі його дочірні процеси.
        :param pid: Ідентифікатор процесу (PID).
        :param include_children: Якщо True, також розморожує всі дочірні процеси.
        :return: True, якщо успішно, False у разі помилки.
        """
        PROCESS_SUSPEND_RESUME = 0x0800
        NTSTATUS = ctypes.c_int

        # Завантажуємо необхідні функції Windows API
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        NtResumeProcess = ctypes.WINFUNCTYPE(NTSTATUS, wintypes.HANDLE)(
            ("NtResumeProcess", ctypes.WinDLL("ntdll"))
        )
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        pids_to_resume = [pid]
        if include_children:
            pids_to_resume.extend(self.get_child_processes(pid))

        success = True
        for pid_to_resume in pids_to_resume:
            process_handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid_to_resume)
            if not process_handle:
                error_code = ctypes.get_last_error()
                if self.dev_mode:  # Якщо dev_mode увімкнено, виводимо повідомлення
                    print(f"Не вдалося відкрити процес PID {pid_to_resume}. Код помилки: {error_code}")
                success = False
                continue

            try:
                status = NtResumeProcess(process_handle)
                if status != 0:
                    if self.dev_mode:
                        print(f"Не вдалося розморозити процес PID {pid_to_resume}. Код помилки: {status}")
                    success = False
                else:
                    if self.dev_mode:
                        print(f"Процес PID {pid_to_resume} успішно розморожено.")
            finally:
                kernel32.CloseHandle(process_handle)

        return success
    
    def resume_selected(self):
        """
        Розморожує вибрані процеси з Listbox.
        """
        selected_programs = self.get_selected_programs()
        if not selected_programs:
            if self.dev_mode:
                print("Жодної програми не вибрано для розморожування.")
                return

        for program_name in selected_programs:
            pids = self.processes.get(program_name, [])
            if not pids:
                if self.dev_mode:
                    print(f"У програми {program_name} немає активних процесів.")
                    continue

            for pid in pids:
                success = self.resume_process(pid, include_children=True)
                self.update_status(program_name, status = "runn")
                if self.dev_mode and success:
                    print(f"Процес PID {pid} і всі його дочірні процеси для програми {program_name} розморожено.")
                else:
                    if self.dev_mode:
                        print(f"Не вдалося розморозити процес PID {pid} для програми {program_name}.")
    
    def load_running_programs(self):
        """Завантажує статуси працюючих програм із файлу, враховуючи пріоритетність статусу з файлу."""
        if os.path.exists('running_programs.json'):
            with open('running_programs.json', 'r', encoding='utf-8') as file:
                running_programs = json.load(file)
                for name, info in running_programs.items():
                    # Визначення PID та перевірка, чи процес існує
                    process_exists = info['pid'] and psutil.pid_exists(info['pid'][0])

                    # Встановлення статусу з файлу (пріоритетний)
                    if 'status' in info:
                        status = info['status']  # Пріоритетний статус
                    else:
                        # Якщо статус не вказаний у файлі, визначаємо за наявністю процесу
                        status = "runn" if process_exists else "stopped"

                    # Оновлення статусу програми
                    if process_exists:
                        self.processes[name] = info['pid']
                    else:
                        self.processes.pop(name, None)

                    # Виклик оновлення статусу в інтерфейсі
                    self.update_status(name, status=status)
    
    
    
    def save_running_programs(self):
        """Зберігає статуси працюючих програм у файл."""
        running_programs = {}
        for name, pids in self.processes.items():
            # Перевіряємо, чи існує ключ 'status' в self.programs
            status = self.programs.get(name, {}).get("status", "stopped")  # Значення за замовчуванням, якщо статус відсутній
            running_programs[name] = {"pid": pids, "status": status}

        with open('running_programs.json', 'w', encoding='utf-8') as file:
            json.dump(running_programs, file, ensure_ascii=False, indent=4)
    

    def check_autorestart(self):
        for program_name, pids in self.processes.items():
            if "autorestart" in self.programs[program_name].get("attributes", []):
                for pid in pids:
                    if not psutil.pid_exists(pid):
                        self.logger.info(f"Program '{program_name}' was closed from outside, restart...")
                        self.launch_program(program_name)

        self.root.after(5000, self.check_autorestart)

    def toggle_hidden_programs(self):
        """Перемикає режим прихованих програм"""
        # Перемикаємо режим прихованих програм
        self.hidden_mode = not self.hidden_mode

        if self.hidden_mode:
            # Зберігаємо поточний filter_attribute і переключаємося на 'hide'
            self._prev_filter_attribute = self.filter_attribute
            self.filter_attribute = 'hide'
        else:
            # Відновлюємо попереднє значення filter_attribute
            self.filter_attribute = self._prev_filter_attribute
            self._prev_filter_attribute = None  # Очищаємо, щоб уникнути плутанини

        # Оновлюємо список програм
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
                self.config_additional = config
                self.programs_file = config.get('programs_file', 'programs.json')
                self.color_code = config.get('color', '#FFFFFF')
                self.text_color = config.get('text_color', '#FFFFFF')
                self.app_geometry = config.get('app_geometry', '600x400')
                self.attributes = config.get('attributes', {})
                self.status_colors = config.get('status_colors', {})
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
                self.lower_console_command = config.get('lower_console_command', 'True').lower() == 'true'
                self.client_notify = config.get('client_notify', 'False').lower() == 'true'
                self.TeServerIntegration = config.get('TeServerIntegration', 'False').lower() == 'true'
                self.notify_missing_program = config.get('notify_missing_program', 'False').lower() == 'true'
                self.banned = config.get('banned', '')
                self.filter_attribute = config.get('filter_attribute', '')
                self.categories = config.get('categories', '[]')
                self.white_list = config.get('white_list', '')
                self.lang = config.get('lang', 'en')
                
                formated_color = {key: value.format(text_color=self.text_color) if isinstance(value, str) else value 
                            for key, value in self.status_colors.items()}
                self.status_colors = formated_color
                
                
                self.additional_menu = config.get('additional_menu', 'True').lower() == 'true'
                self.interface_meny_ = config.get('interface_meny_', 'True').lower() == 'true'
                self.file_menu_ = config.get('file_menu_', 'True').lower() == 'true'
                self.use_search_bar_ = config.get('use_search_bar_', 'True').lower() == 'true'
                self.use_context_menu = config.get('use_context_menu', 'True').lower() == 'true'
                self.use_scrollbar = config.get('use_scrollbar', 'True').lower() == 'true'
                self.use_details_label = config.get('use_details_label', 'True').lower() == 'true'
                self.add_hide_details_panel_btn = config.get('add_hide_details_panel_btn', 'True').lower() == 'true'
                
                self.hotkeys = {key: getattr(self, func, None) for key, func in config.get('hotkeys', {}).items()}
                self.commands = {cmd: getattr(self, func, None) for cmd, func in config.get('commands', {}).items()}
                self.descriptions = config.get('descriptions', {})


    def setup_logging(self):
        self.logger = logging.getLogger("AppLauncher")
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(self.log_file, maxBytes=10000000000000, backupCount=3)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)


    def add_program(self):
        program_name = simpledialog.askstring(self.loc._("program_name_title"), self.loc._("program_name_prompt"))
        if program_name:
            program_path = filedialog.askopenfilename(title=self.loc._("select_program_title"))
            if program_path:
                attributes = simpledialog.askstring(self.loc._("attributes_title"), self.loc._("attributes_prompt"))
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
    
    def handle_launch_command(self, *args):
        print(*args)
        """
        Обробляє команду запуску програм із аргументів, переданих через консоль.
        
        Параметри:
            *args: список аргументів, що містять назви програм у лапках, розділені комами.
        """
        if not args:
            self.logger.error("No program name provided in the arguments.")
            return

        # Об'єднуємо аргументи в один рядок, якщо їх кілька (наприклад, передано через консоль)
        joined_args = " ".join(args).strip()

        # Розділяємо назви програм за комами, видаляючи зайві пробіли та лапки
        try:
            program_names = [
                name.strip().strip('"').strip("'")
                for name in joined_args.split(",")
                if name.strip()
            ]
        except Exception as e:
            self.logger.error(f"Error parsing program names: {e}")
            return

        if not program_names:
            self.logger.error("No valid program names found after parsing.")
            return

        # Якщо є лише одна програма, передаємо її як program_name
        if len(program_names) == 1:
            self.launch_program(program_name=program_names[0])
        else:
            # Якщо є кілька програм, передаємо їх як program_names
            self.launch_program(program_names=program_names)
    
    def launch_program(self, program_name=None, program_names=None):
        """
        Запускає одну або кілька програм. 
        :param program_name: Назва програми для запуску (якщо запускається одна програма).
        :param program_names: Список назв програм для запуску (якщо запускається кілька програм).
        """
        # Якщо передано тільки одну програму, формуємо список з однієї назви
        if program_name and not program_names:
            program_names = [program_name]

        # Якщо обидва параметри порожні, визначаємо список програм зі списку GUI
        if not program_names:
            if self.mainFrame == 'MAIN':
                selected = self.listbox.curselection()
                if selected:
                    program_names = [self.listbox.get(i).split(" (")[0] for i in selected]
            else:
                print('')

        # Якщо список програм все ще порожній, нічого не робимо
        if not program_names:
            return

        # Запускаємо всі програми у списку
        for program_name in program_names:
            program_info = self.programs.get(program_name)
            if not program_info:
                continue

            self.apply_attributes(program_info)

            try:
                self.flag_new_console = program_info.get("self_console", "").lower() == 'true'
            except Exception:
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
                self.update_status(program_name, status = "runn")
                self.logger.info(f"Program '{program_name}' launched with the command: {command}")
                self.save_programs()
                self.save_running_programs()
            except Exception as e:
                #self.update_status(program_name, f"Error: {e}")
                print(e)
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
    

    
    def update_program_list_with_search(self, event=None):
        if self.mainFrame == 'MAIN':
            # Отримуємо пошуковий термін
            search_term = self.search_var.get().strip().lower() if self.search_var else ""
            filtered_programs = {}

            # Перебираємо всі програми
            for name, info in self.programs.items():
                attributes = info.get("attributes", [])

                # Перевірка пошукового терміну
                if search_term and search_term not in name.lower():
                    continue  # Пропускаємо програми, які не відповідають пошуку

                # Логіка для режиму прихованих програм
                is_hidden = "hide" in attributes
                if self.hidden_mode and not is_hidden:
                    continue  # Пропускаємо неприховані програми
                elif not self.hidden_mode and is_hidden:
                    continue  # Пропускаємо приховані програми

                # Додатковий фільтр за атрибутами
                if self.filter_attribute and self.filter_attribute != "NoneAtr":
                    if self.filter_attribute not in attributes:
                        continue  # Пропускаємо програми, якщо атрибут не відповідає

                # Додаємо програму до відфільтрованого списку
                filtered_programs[name] = info

            # Завантажуємо статуси з running_programs.json
            

            # Якщо є відфільтровані програми, оновлюємо список
            if filtered_programs:
                # Оновлюємо відображення програми в Listbox
                self.refresh_program_list(filtered_programs)
                self.load_running_programs()
            else:
                # Якщо немає збігів, не відображаємо програми або виводимо повідомлення
                self.listbox.delete(0, tk.END)  # Очищаємо список
                self.listbox.insert(tk.END, self.loc._("search_not_found"))  # Повідомлення про відсутність збігів

    
    def close_program(self):
        if self.mainFrame == 'MAIN':
            selected = self.listbox.curselection()
            if selected:
                program_names = [self.listbox.get(i).split(" (")[0] for i in selected]

                for program_name in program_names:
                    if program_name in self.processes and self.processes[program_name]:
                        for pid in self.processes[program_name]:
                            self.terminate_process_tree(pid)
                            start_time = self.start_times.pop(pid, None)
                            if start_time:
                                elapsed_time = time.time() - start_time
                                self.programs[program_name]["total_runtime"] += elapsed_time
                                self.logger.info(f"Program '{program_name}' (PID: {pid}) completed in {elapsed_time:.2f} seconds")
                        self.processes[program_name] = []
                        self.update_status(program_name, status = "stopped")
                        self.save_programs()
                        self.save_running_programs()

                        # Перевірка на атрибут 'refresh'
                        if "refresh" in self.programs[program_name].get("attributes", []):
                            self.logger.info(f"Reloading 'programs.json' after completing the program '{program_name}'")
                            self.load_programs_and_refresh()
                    else:
                        self.update_status(program_name, status = "stopped")
                        self.logger.info(f"Attempted to end the program '{program_name}', which was not running")
        else:
            print('')


    def terminate_process_tree(self, pid):
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            psutil.wait_procs(children, timeout=10)
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
            self.load_running_programs()
            self.check_programs_status()
        else:
            print(self.loc._("func_only_work_in_mainfraim"))

    def refresh_program_list(self, programs=None):
        """Оновлює список програм у Listbox із врахуванням поточних статусів."""
        self.listbox.delete(0, tk.END)  # Очистити список
        programs = programs or self.programs  # Використовувати поточний словник програм

        for program_name, program_info in programs.items():
            attributes = program_info.get("attributes", [])
            status = program_info.get("status", "stopped")  # Брати статус лише зі словника
            color = self.status_colors.get(status, self.text_color)

            # Режим прихованих програм
            is_hidden = "hide" in attributes
            if self.hidden_mode and not is_hidden:
                continue
            elif not self.hidden_mode and is_hidden:
                continue

            # Фільтрація за атрибутами
            if self.filter_attribute == 'NoneAtr':
                pass
            elif self.filter_attribute and self.filter_attribute not in attributes:
                continue

            # Додавання програми до списку
            self.listbox.insert(tk.END, program_name)
            if self.listbox.size() > 0:
                self.listbox.itemconfig(tk.END, fg=color)

    def open_file_location(self):
        selected = self.listbox.curselection()
        if selected:
            if len(selected) > 1:
                return

            listbox_entry = self.listbox.get(selected[0])
            program_name = listbox_entry.split(" (")[0]
            program_info = self.programs.get(program_name)

            if program_info:
                file_path = program_info.get("path")
                if file_path and os.path.exists(file_path):
                    folder_path = os.path.dirname(file_path)
                    os.startfile(folder_path)
                else:
                    messagebox.showerror(self.loc._("error"), self.loc._("file_not_found2"))



    def update_status(self, program_name, status=None, color=None):
        """Оновлює статус і колір програми та зберігає ці зміни у файл running_programs.json."""
        if program_name not in self.programs:
            return  # Програма не знайдена

        # Завантаження поточного стану running_programs
        running_programs = {}
        if os.path.exists('running_programs.json'):
            with open('running_programs.json', 'r', encoding='utf-8') as file:
                running_programs = json.load(file)

        # Оновлення статусу у running_programs
        running_programs[program_name] = running_programs.get(program_name, {})
        running_programs[program_name]["status"] = status
        running_programs[program_name]["pid"] = self.processes.get(program_name, [])

        # Збереження змін у файл
        with open('running_programs.json', 'w', encoding='utf-8') as file:
            json.dump(running_programs, file, ensure_ascii=False, indent=4)

        # Оновлення кольору статусу
        if color:
            self.status_colors[status] = color

        # Оновлення інтерфейсу Listbox
        for index in range(self.listbox.size()):
            listbox_entry = self.listbox.get(index)
            if listbox_entry == program_name:
                new_color = self.status_colors.get(status, self.text_color)
                self.listbox.itemconfig(index, fg=new_color)
                break
    
    def get_programs_by_status(self, status):
        """
        Отримує список програм із вказаним статусом.

        Args:
            status (str): Статус для пошуку.

        Returns:
            list: Список назв програм із вказаним статусом.
        """
        programs_with_status = [
            program_name for program_name, program_info in self.programs.items()
            if program_info.get("status") == status
        ]

        return programs_with_status
    
    def get_status(self, program_name):
        """
        Отримує статус програми зі збережених даних.

        Args:
            program_name (str): Назва програми.

        Returns:
            str: Статус програми або None, якщо статус не знайдено.
        """
        program_info = self.programs.get(program_name)
        if program_info:
            return program_info.get("status")
        return None
    
    def show_program_details(self, event = None):
        if self.use_details_label:
            self.selected_program()
            selected = self.listbox.curselection()
            if selected:
                if len(selected) > 1:
                    return
            if selected:
                listbox_entry = self.listbox.get(selected)
                program_name = listbox_entry.split(" (")[0]
                program_info = self.programs.get(program_name, {})

                if not program_info:
                    details = self.loc._("no_info_found")
                else:
                    total_runtime = program_info.get("total_runtime", 0.0)
                    hours = int(total_runtime // 3600)  # Повні години
                    minutes = int((total_runtime % 3600) // 60)  # Повні хвилини
                    
                    attributes = program_info.get('attributes', [])
                    if isinstance(attributes, list):
                        attributes_str = ', '.join(attributes)
                    else:
                        attributes_str = str(attributes)

                    details = (
                                f"{self.loc._('category')}: {self.filter_attribute}\n"
                                f"{self.loc._('program_name')}: {program_name}\n"
                                f"{self.loc._('launch_count')}: {program_info.get('launch_count', 0)}\n"
                                f"{self.loc._('total_runtime')}: {hours} {self.loc._('hours')} {minutes} {self.loc._('minutes')}\n"
                                #f"{self.loc._('category')}: {program_info.get('attributes', '')}\n"
                                f"{self.loc._('category')}: {attributes_str}\n"
                                f"{self.loc._('program_description')}: {program_info.get('description', '')}\n"
                                )
                    self.program_details = details
                self.details_label.config(width= 30, text=details)
                self.updata_panell()
            else:
                self.details_label.config(text=self.loc._("select_program"))
    
    def hide_details_panel(self):
        self.details_label.config(width=0, text="")
    
    def updata_panell(self):
        program_details = self.program_details
        program_details = self.program_details + f"\n\nCPU: {round(self.monitor.get_cpu_load(), 0)}%,\nMemory usage: {round(self.monitor.get_memory_usage(), 0)}%\n\n"
        self.details_label.config(width= 30, text=program_details, fg = self.text_color)
        self.root.after(800, self.updata_panell)

    def edit_program(self):
        selected = self.listbox.curselection()
        if selected:
            if len(selected) > 1:
                return

            listbox_entry = self.listbox.get(selected[0])
            program_name = listbox_entry.split(" (")[0]

            new_name = simpledialog.askstring(self.loc._("edit_program"), self.loc._("new_program_name"), initialvalue=program_name)
            new_path = filedialog.askopenfilename(title=self.loc._("new_program_path"))

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
            if len(selected) > 1:
                return

            listbox_entry = self.listbox.get(selected[0])
            program_name = listbox_entry.split(" (")[0]

            # Перевірка на наявність атрибута 'sys'
            if "sys" in self.programs.get(program_name, {}).get("attributes", []):
                messagebox.showerror(self.loc._("error"), self.loc._("error_program_del_denied").format(program_name=program_name))
                return

            # Діалогове вікно підтвердження
            confirm = messagebox.askyesno(self.loc._("confirmation_title"), self.loc._("confirmation_message").format(program_name=program_name))
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
                    self.update_status(program_name, "stopped" if not self.processes[program_name] else "runn")
        self.root.after(2000, self.check_programs_status)  # Перевірка кожні 2 секунди



    def create_interface(self, frame=None):
        frame = self.main_frame
        # Очищення фрейму перед заповненням
        for widget in frame.winfo_children():
            widget.destroy()
        
        self.use_listbox = True
        
        # Конфігурація вікна
        self.root.title(self.loc._("window_title"))
        self.root.geometry(self.app_geometry)
        self.root.configure(bg=self.color_code)
        
        
        if self.use_search_bar_:
            self.create_search_bar(frame)
        self.root.iconbitmap('icon.ico')

        # Верхнє меню
        menubar = Menu(self.root, bg="#f7f7f7", fg="black", font=("Arial", 10))
        
        # Вкладка "Файл"
        if self.file_menu_:
            file_menu = Menu(menubar, tearoff=0, bg="#f7f7f7", fg="black", font=("Arial", 9))
            file_menu.add_command(label=self.loc._("add_program"), command=self.add_program)
            file_menu.add_command(label=self.loc._("clear_cache_file"), command=self.clear_running_programs)
            file_menu.add_command(label=self.loc._("open_script_folder"), command=self.open_script_folder)
            file_menu.add_command(label=self.loc._("program_manager"), command=self.launch_program_manager)
            menubar.add_cascade(label=self.loc._("file"), menu=file_menu)

        # Вкладка "Інтерфейс"
        if self.interface_meny_:
            interface_menu = Menu(menubar, tearoff=0, bg="#f7f7f7", fg="black", font=("Arial", 9))
            interface_menu.add_command(label=self.loc._("change_interface_color"), command=self.choose_color)
            interface_menu.add_command(label=self.loc._("change_text_color"), command=self.choose_text_color)
            interface_menu.add_command(label=self.loc._("save_color_to_config"), command=self.save_color_to_config)
            interface_menu.add_command(label=self.loc._("save_text_color_to_config"), command=self.save_text_color_to_config)
            interface_menu.add_command(label=self.loc._("show_hidden_programs"), command=self.toggle_hidden_programs)
            menubar.add_cascade(label=self.loc._("interface"), menu=interface_menu)
            
            
        self.category_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self.loc._("category"), menu=self.category_menu)
            
        # Вкладка "Додаткове"
        if self.additional_menu:
            extra_menu = Menu(menubar, tearoff=0, bg="#f7f7f7", fg="black", font=("Arial", 9))
            extra_menu.add_command(label=self.loc._("reload_programs_list"), command=self.load_programs_and_refresh)
            extra_menu.add_command(label=self.loc._("toggle_console_visibility"), command=self.toggle_console_visibility)
            extra_menu.add_command(label=self.loc._("toggle_launcher_window_visibility"), command=self.toggle_visibility_window)
            extra_menu.add_command(label=self.loc._("restart_launcher"), command=self.restart_script)
            if self.add_hide_details_panel_btn:
                extra_menu.add_command(label=self.loc._("hide_details_panel"), command=self.hide_details_panel)
            extra_menu.add_command(label=self.loc._("exit"), command=self.exit_app_from_menu)
            menubar.add_cascade(label=self.loc._("extra"), menu=extra_menu)

        self.root.config(menu=menubar)

        # Пошуковий рядок - якщо створюється функція create_search_bar, можна додати стиль
        # Список програм
        if self.use_listbox:
            self.listbox = tk.Listbox(frame, bg="white", fg="black", font=("Arial", 11), selectbackground="#a688ff", borderwidth=2, relief="groove")
            self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
            self.listbox.bind("<Double-1>", self.on_listbox_double_click)
            self.listbox.bind("<Button-3>", self.show_context_menu)
            self.listbox.bind("<ButtonRelease-1>", self.show_program_details)

        # Налаштування скролбара
        if self.use_scrollbar:
            scrollbar = tk.Scrollbar(frame, command=self.listbox.yview, troughcolor="#e0e0e0", bg="#d0d0d0", activebackground="#a0a0a0", width=10, relief="flat")
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.listbox.config(yscrollcommand=scrollbar.set)

        # Панель деталей без чорної обводки
        if self.use_details_label:
            self.details_label = tk.Label(frame, bg="#f0f0f0", fg="black", font=("Arial", 10), justify=tk.LEFT, anchor="nw", wraplength=300, padx=10, pady=10)
            self.details_label.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        # Контекстне меню
        if self.use_context_menu:
            self.context_menu = tk.Menu(self.root, tearoff=0, bg="#ffffff", fg="black", font=("Arial", 9))
            self.context_menu.add_command(label=self.loc._("launch"), command=self.launch_program)
            self.context_menu.add_command(label=self.loc._("stop"), command=self.close_program)
            self.context_menu.add_command(label=self.loc._("freeze_program"), command=self.suspend_selected)
            self.context_menu.add_command(label=self.loc._("unfreeze_program"), command=self.resume_selected)
            self.context_menu.add_command(label=self.loc._("edit"), command=self.edit_program)
            self.context_menu.add_command(label=self.loc._("delete"), command=self.delete_program)
            self.context_menu.add_command(label=self.loc._("open_file_location"), command=self.open_file_location)

        # Оновлення списку програм
        self.refresh_program_list()
        self.check_programs_status()

        
        
    def create_search_bar(self, frame):
        self.search_var = tk.StringVar()
        self.search_bar = tk.Entry(frame, textvariable=self.search_var, bg=self.color_code, fg="black")
        self.search_bar.pack(fill=tk.X, pady=1)  # Додаємо параметр `pady` для відступу зверху
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
        color_code = colorchooser.askcolor(title=self.loc._("chose_color"))
        if color_code[1]:  # Якщо колір вибрано
            print(color_code)

            self.update_background(color_code[1])
            self.color_code = color_code[1]
            
    def choose_text_color(self):
        # Відкриття діалогу для вибору кольору
        text_color = colorchooser.askcolor(title=self.loc._("chose_color"))
        if text_color[1]:  # Якщо колір вибрано
            print(text_color)

            self.text_color = text_color[1]
            self.refresh_program_list()
            

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

            # Локалізоване повідомлення про успіх
            success_message = self.loc._("color_saved_success").format(color=self.color_code, config_file=config_file)
            print(success_message)

        except FileNotFoundError:
            print(self.loc._("file_not_found").format(config_file=config_file))
        except json.JSONDecodeError:
            print(self.loc._("json_decode_error"))
        except Exception as e:
            print(self.loc._("generic_error").format(error=str(e)))
            
    def save_text_color_to_config(self, config_file='config.json'):
        print(self.text_color)
        try:
            # Відкриваємо файл з налаштуваннями
            with open(config_file, 'r', encoding='utf-8') as file:
                config = json.load(file)

            # Оновлюємо значення кольору
            config['text_color'] = self.text_color

            # Записуємо зміни назад у файл
            with open(config_file, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=4)

            # Локалізоване повідомлення про успіх
            success_message = self.loc._("color_saved_success").format(color=self.text_color, config_file=config_file)
            print(success_message)

        except FileNotFoundError:
            print(self.loc._("file_not_found").format(config_file=config_file))
        except json.JSONDecodeError:
            print(self.loc._("json_decode_error"))
        except Exception as e:
            print(self.loc._("generic_error").format(error=str(e)))

    def update_background(self, color):
        # Оновлення кольору фону головного вікна
        if self.mainFrame == 'MAIN':
            self.root.config(bg=color)
            if self.use_listbox:
                self.listbox.config(bg=color)
            if self.use_details_label:
                self.details_label.config(bg=color)
            if self.use_search_bar_:
                self.search_bar.config(bg=color)
            if self.use_context_menu:
                self.context_menu.config(bg=color)
            # Видалення верхнього меню, якщо воно існує
            self.root.config(menu=None)
            print(self.loc._("color_change_secces"))
            print(color)
        else:
            print('')

      
      
    def with_start_update_background(self, color):
        # Оновлення кольору фону головного вікна
        if self.mainFrame == 'MAIN':
            self.root.config(bg=color)
            if self.use_listbox:
                self.listbox.config(bg=color)
            if self.use_details_label:
                self.details_label.config(bg=color)
            if self.use_search_bar_:
                self.search_bar.config(bg=color)
            if self.use_context_menu:
                self.context_menu.config(bg=color)
            # Видалення верхнього меню, якщо воно існує
            self.root.config(menu=None)
            #print("Color change and menubar removal successful")
            #print(color)
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


    def toggle_visibility(self):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
        else:
            self.root.withdraw()

    def run_in_tray(self):
    # Створюємо спрощене меню трея
        menu = TrayMenu(
            TrayMenuItem(self.loc._("tray_window_button"), self.toggle_visibility),
            TrayMenu.SEPARATOR, 
            TrayMenuItem(self.loc._("tray_console_button"), self.toggle_console_visibility),
            TrayMenu.SEPARATOR,
            TrayMenuItem(self.loc._("restart_launcher"), self.restart_script),
            TrayMenu.SEPARATOR,  # Розділювач
            TrayMenuItem(self.loc._("tray_exit_button"), self.exit_app)  # Кнопка для виходу з програми
        )
        self.icon = Icon(self.loc._("app_title_tray"), self.create_image(), self.loc._("app_title_tray"), menu)
        self.icon.run()
        


    def exit_app(self, icon):
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
            # Якщо утримується Ctrl, закриваємо програму
            if event.state & 0x4:  # Перевіряє стан клавіші Ctrl
                self.close_program()
            else:
                self.launch_program(program_name, None)
                
    def take_screenshot(self):
        try:
        
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            screenshot_path = os.path.join(os.getcwd(), f'screenshot_{timestamp}.png')

        
            screenshot = ImageGrab.grab()
            screenshot.save(screenshot_path)

        
            subprocess.Popen(['mspaint', screenshot_path], creationflags=subprocess.CREATE_NO_WINDOW)

        except Exception as e:
            print(f"Виникла помилка: {e}")
    

    def restart_script(self):
        """
        Знаходить шлях до першого скрипта і передає його другому скрипту для запуску.
        """
        # Знаходимо шлях до поточного скрипта
        script_path = os.path.realpath(sys.argv[0])  # Повний шлях до першого скрипта
        second_script_path = os.path.join(os.path.dirname(script_path), 'restart.pyw')  # Шлях до другого скрипта

        if os.path.exists(second_script_path):
            subprocess.Popen([sys.executable, second_script_path, script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.exit_app_from_menu()
        else:
            print("Не знайдено другого скрипта!")

    
if __name__ == "__main__":
    root = tk.Tk()
    app = AppLauncher(root)
    root.mainloop()
