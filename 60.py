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
from tkinter import ttk
from tkinter import simpledialog, filedialog, messagebox
from tkinter import Menu
from tkinter import colorchooser
import logging
from logging.handlers import RotatingFileHandler
import platform
import psutil
from pystray import Icon, Menu as TrayMenu, MenuItem as TrayMenuItem
from PIL import Image, ImageDraw, ImageGrab
import keyboard
from UniClient import Client
from locales import Localization
from SystemMonitor import SystemMonitor
from Console import Console
#print("All import done")

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
        self.displays_datails_panel = True
        self.attributes = {}
        self.categories = [""]
        self.filter_attribute = "NoneAtr"
        self.status_colors = {}
        self.app_map = {}
        self.restart_script_file_name = 'restart.pyw'
        self.stats_dir = "stats"
        self.name_check_interval = 20
        self.additional_processes = []
        self.launcher_additional_notify = False
        self.load_config()
        self.logo = """_________ _______  _______  _______           _        _______
\\__   __/(  ____ \\(       )(  ___  )|\\     /|( (    /|(  ____ \\
   ) (   | (    \\/| () () || (   ) || )   ( ||  \\  ( || (    \\/
   | |   | (__    | || || || (___) || |   | ||   \\ | || (__
   | |   |  __)   | |(_)| ||  ___  || |   | || (\\ \\) ||  __)
   | |   | (      | |   | || (   ) || |   | || | \\   || (
   | |   | (____/\\| )   ( || )   ( || (___) || )  \\  || (____/\\
   )_(   (_______/|/     \\||/     \\|(_______)|/    )_)(_______/
        """
        print(self.logo)
        if not self.dev_mode:
            self.disable_console_close_button()
        self.hide_console_with_start()
        self.loc = Localization(locale=self.lang)
        self.loc.set_locale(locale=self.lang)
        if self.launcher_additional_notify: 
            print(self.loc._("config_load"))
        self.log_file = "launcher.log"
        self.programs = {}
        self.processes = {}
        self.start_times = {}
        self.setup_logging()
        self.protect_mode = False
        self.info_window = None
        

        self.root.bind("<Return>", lambda _: self.launch_program())
        self.root.bind("<Control-Return>", lambda _: self.close_program())


        os.makedirs(self.stats_dir, exist_ok=True)
        
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
        if self.launcher_additional_notify: 
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
            if self.launcher_additional_notify: 
                print(self.loc._("client_start"))
        # Запускаємо окремий потік для обробки повідомлень від інших клієнтів
            self.receive_thread = threading.Thread(target=self.client.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            if self.launcher_additional_notify: 
                print(self.loc._("start_receive_messages"))
        #self.check_for_messages()
            self.root.after(500, self.check_for_messages)
        
            self.connect = threading.Thread(target=self.client.start)
            self.connect.daemon = True
            self.connect.start()
        
        self.registered_hotkeys = set()
        self.start_keyboard_listener()
        if self.launcher_additional_notify: 
            print(self.loc._("keyboard_listener_statr"))

        self.console_thread = threading.Thread(target=self.console)
        self.console_thread.daemon = True  # Потік завершиconsole_thread_startться разом із програмою
        self.console_thread.start()
        if self.launcher_additional_notify: 
            print(self.loc._("console_thread_start"))
        
        check_executable_thread = threading.Thread(target=self.check_executables, daemon=True)
        check_executable_thread.start()
        self.load_programs_and_refresh() 

        self.processes_call = self._load_processes_from_file()
        self.monitoring_thread = None
        self.monitoring_active = False

        
        self.start_monitoring_additional_processes()
    
    def create_console_window(self):
        settings = {
        "title": "Custom Console",
        "geometry": "800x600",
        "bg_color": "#2c333b",
        "fg_color": "black"
    }
        frame = self.main_frame
        self.console = Console(frame, settings)
        self.console.set_command_handler(self.execute_launcher_command)
        self.console.open_console_window()
    
    def _save_processes_to_file(self):
        """Зберігає дані про процеси у файл launcher_aditional.json."""
        data = {"call_program": self.processes_call}
        try:
            with open("launcher_aditional.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.logger.info(f"Error saving processes: {e}")
            print(f"Error saving processes: {e}")

    def _load_processes_from_file(self):
        """Завантажує дані про процеси з файлу launcher_aditional.json."""
        if not os.path.exists("launcher_aditional.json"):
            return {}

        try:
            with open("launcher_aditional.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("call_program", {})
        except Exception as e:
            self.logger.info(f"Error loading processes: {e}")
            print(f"Error loading processes: {e}")
            return {}

    def _check_additional_processes(self):
        """Перевіряє додаткові процеси на існування та додає їх до processes_call."""
        found_processes = set()  # Для запобігання дублюванню
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            try:
                process_name = proc.info['name']
                for target_name in self.additional_processes:
                    if process_name.lower() == target_name.lower():
                        pid = proc.info['pid']
                        if target_name not in self.processes_call:
                            self.processes_call[target_name] = []
                        if pid not in self.processes_call[target_name]:
                            self.processes_call[target_name].append(pid)
                            found_processes.add(target_name)
                            self.logger.info(f"Found process: {target_name} with PID {pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        if found_processes:
            self._save_processes_to_file()

    def _monitor_additional_processes(self):
        """Фоновий процес для моніторингу додаткових процесів."""
        last_name_check = time.time()
        while self.monitoring_active:
            # Перевірка PID у processes_call
            for process_name, pids in list(self.processes_call.items()):
                for pid in list(pids):
                    if not psutil.pid_exists(pid):
                        self.processes_call[process_name].remove(pid)
                        if not self.processes_call[process_name]:
                            del self.processes_call[process_name]
                            self._save_processes_to_file()

            # Перевірка за іменами раз на 20 секунд
            if time.time() - last_name_check >= self.name_check_interval:
                self._check_additional_processes()
                last_name_check = time.time()

            time.sleep(1)

    def start_monitoring_additional_processes(self):
        """Запускає фоновий потік для моніторингу додаткових процесів."""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitor_additional_processes, daemon=True)
        self.monitoring_thread.start()

    def stop_monitoring_additional_processes(self):
        """Зупиняє моніторинг додаткових процесів."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join()

    def call_program(self, name):
        """
        Викликає програму або відкриває файл на основі імені у словнику.
        Запускає підпроцеси та додає їхні PID у self.processes_call.
        """
        if name not in self.app_map:
            print(self.loc._("not_found_in_dictionary").format(name=name))
            return

        entry = self.app_map[name]

        if isinstance(entry, str):
            path = os.path.abspath(entry) if not os.path.isabs(entry) else entry
            working_dir = os.path.dirname(path)

            try:
                process = None
                if platform.system() == "Windows":
                    if path.endswith(".py"):
                        process = subprocess.Popen(["python", path], shell=True, cwd=working_dir)
                    elif path.endswith(".exe"):
                        process = subprocess.Popen([path], shell=True, cwd=working_dir)
                    else:
                        os.startfile(path)
                else:
                    open_command = ["xdg-open", path] if platform.system() == "Linux" else ["open", path]
                    process = subprocess.Popen(open_command, cwd=working_dir)

                if process:
                    self.processes_call.setdefault(name, []).append(process.pid)
                    self._save_processes_to_file()

            except Exception as e:
                print(self.loc._("error_with_start").format(name=name, e=e))

        elif isinstance(entry, list):
            path = entry[0]
            args = entry[1:]
            path = os.path.abspath(path) if not os.path.isabs(path) else path
            working_dir = os.path.dirname(path)

            try:
                command = ["python", path] + args if path.endswith(".py") else [path] + args
                process = subprocess.Popen(command, cwd=working_dir)
                self.processes_call.setdefault(name, []).append(process.pid)
                self._save_processes_to_file()

            except Exception as e:
                print(self.loc._("error_with_start").format(name=name, e=e))

    def terminate_program(self, pid, name):
        """Закриває процес за PID і видаляє його з словника."""
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except Exception as e:
            print(e)

        if name in self.processes_call:
            self.processes_call[name].remove(pid)
            if not self.processes_call[name]:
                del self.processes_call[name]

            self._save_processes_to_file()

    def restart_program(self, pid, name):
        """Перезапускає програму за PID."""
        try:
            proc = psutil.Process(pid)
            exe_path = proc.exe()
            working_dir = os.path.dirname(exe_path)

            self.terminate_program(pid, name)

            if exe_path.endswith(".py"):
                subprocess.Popen(["python", exe_path], shell=True, cwd=working_dir)
            else:
                subprocess.Popen([exe_path], cwd=working_dir, creationflags=subprocess.CREATE_NEW_CONSOLE)

            print(self.loc._("process_restarted").format(name=name))
        except Exception as e:
            print(f"{name} {e}")

    def update_listbox(self, listbox):
        """Оновлює вміст listbox."""
        listbox.delete(0, tk.END)
        for name, pids in self.processes_call.items():
            for pid in pids:
                listbox.insert(tk.END, f"{name} (PID:{pid})")

    def display_process_list(self):
        """Створює вікно із списком запущених процесів і оновлює його періодично."""
        def on_double_click(event):
            selected = listbox.curselection()
            if not selected:
                return

            index = selected[0]
            item_text = listbox.get(index)

            # Розбір PID та імені програми
            try:
                name, pid_text = item_text.rsplit(" (PID:", 1)
                pid = int(pid_text.strip(")"))
                self.terminate_program(pid, name)
                listbox.delete(index)
            except ValueError:
                print(self.loc._("invalid_process_entry").format(entry=item_text))

        def on_context_menu(event):
            try:
                selected = listbox.curselection()
                if not selected:
                    return

                index = selected[0]
                item_text = listbox.get(index)

                name, pid_text = item_text.rsplit(" (PID:", 1)
                pid = int(pid_text.strip(")"))

                context_menu = tk.Menu(window, tearoff=0, bg="white", fg="black")
                context_menu.add_command(label=self.loc._("restart"), command=lambda: self.restart_program(pid, name))
                context_menu.add_command(label=self.loc._("terminate"), command=lambda: self.terminate_program(pid, name))
                context_menu.post(event.x_root, event.y_root)
            except ValueError:
                print(self.loc._("invalid_process_entry").format(entry=item_text))

        def refresh_listbox():
            while not closed:
                listbox.delete(0, tk.END)
                for name, pids in self.processes_call.items():
                    for pid in pids:
                        listbox.insert(tk.END, f"{name} (PID:{pid})")
                time.sleep(2)

        def on_close():
            nonlocal closed
            closed = True
            window.destroy()

        # Створення вікна
        window = tk.Toplevel(self.main_frame)
        window.iconbitmap("icon.ico")
        window.title(self.loc._("process_list_title"))
        window.configure(bg=self.color_code)
        closed = False

        listbox = tk.Listbox(window, width=50, height=20, bg=self.color_code, fg="white", selectbackground="blue")
        listbox.pack(fill=tk.BOTH, expand=True)

        listbox.bind("<Double-1>", on_double_click)
        listbox.bind("<Button-3>", on_context_menu)

        # Додавання кнопки закриття
        close_button = tk.Button(window, text=self.loc._("close"), command=on_close, bg=self.color_code, fg="white")
        close_button.pack(pady=5)

        # Оновлення списку процесів у потоці
        threading.Thread(target=refresh_listbox, daemon=True).start()

        # Обробник закриття вікна
        window.protocol("WM_DELETE_WINDOW", on_close)



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
    
    def check_executables(self, first_run=True, in_cycle=True):
        """
        Перевіряє наявність файлів виконуваних програм і статусів.

        Параметри:
            first_run (bool): Чи викликається ця функція вперше (True за замовчуванням).
        """
        if not self.programs:
            if first_run:
                print(self.loc._("program_list_not_load_or_empty"))
            return

        # Отримуємо список програм зі статусом "not_found"

        # Після оновлення статусів перевіряємо всі програми
        missing_programs = []
        updated_programs = []

        for program_name, program_info in self.programs.items():
            program_path = program_info.get("path")
            current_status = program_info.get("status")

            if not program_path or not os.path.exists(program_path):
                if current_status != "not_found":
                    self.update_status(program_name, status="not_found")
                    missing_programs.append(program_name)
            else:
                if current_status == "not_found":
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
                if self.launcher_additional_notify: 
                    print(self.loc._("all_executable_file_found"))

        # Лог для оновлених програм
        if updated_programs:
            print(self.loc._("program_status_updated"))
            for program in updated_programs:
                print(f" - {program}: stopped")

        # Оновлення списку відсутніх програм у пам'яті
        self.missing_programs = missing_programs
        # Запланувати повторну перевірку через 10 секунд
        if in_cycle:
        
            self.root.after(10000, lambda: self.check_executables(first_run=False, in_cycle=True))


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
    
    def execute_script_func(self, script_name, script_args):

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
    
    def execute_launcher_command(self, command):
        command = command.strip()  # Отримуємо команду
        if command:
            args = command.split()  # Розділяємо команду і аргументи
            if self.lower_console_command:
                args[0] = args[0].lower()
            else:
                args[0] = args[0]
            if len(args) > 0:  # Перевіряємо, чи є в команді аргументи
                if args[0] == "exit":
                    self.exit_app_from_menu()
                elif args[0] in self.commands:
                    self.root.after(0, self.commands[args[0]], *args[1:])  # Виконуємо команду з аргументами
                else:
                    if self.if_not_command:
                        try:
                            subprocess.run(command, shell=True)
                        except Exception as e:
                            self.console.append_output(self.loc._("execution_error").format(error=e))
                    else:
                        self.console.append_output(f"{self.loc._('unknown_command2').format(cmd=args[0])}\n")
            else:
                pass
    
                
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
        try:
            """Завантажує статуси працюючих програм із файлу, враховуючи пріоритетність статусу з файлу."""
            if os.path.exists('running_programs.json'):
                with open('running_programs.json', 'r', encoding='utf-8') as file:
                    running_programs = json.load(file)
                    self.running_programs = running_programs
                    for name, info in running_programs.items():
                        # Визначення PID та перевірка, чи процес існує
                        process_exists = info['pid'] and psutil.pid_exists(info['pid'][0])

                        # Встановлення статусу з файлу (пріоритетний)
                        if 'status' in info:
                            status = info['status']  # Пріоритетний статус з файлу
                        else:
                            # Якщо статус не вказаний у файлі, визначаємо за наявністю процесу
                            status = "runn" if process_exists else "stopped"

                        # Логіка зміни статусу програми
                        if status == "stopped" and process_exists:
                            status = "runn"  # Змінюємо на "runn", якщо процес існує
                        elif not process_exists and status != "runn":
                            status = "stopped"  # Якщо процес не існує і статус не "runn", ставимо "stopped"

                        # Оновлення процесів
                        if process_exists:
                            self.processes[name] = info['pid']
                        else:
                            self.processes.pop(name, None)

                        # Оновлення статусу програми в інтерфейсі
                        self.update_status(name, status=status)
                        # Визначення, чи потрібно зберегти зміни статусу
                        if status == "runn" or status == "stopped":
                            self.save_running_programs()  # Зберігаємо статуси змінених програм
        except Exception as e:
            print(e)
            self.clear_running_programs()
            self.load_running_programs()
    
    
    def save_running_programs(self):
        """Зберігає статуси працюючих програм у файл."""
        running_programs = {}
        
        for name, pids in self.processes.items():
            # Перевіряємо, чи існує ключ 'status' в self.programs
            status = self.running_programs.get(name, {}).get("status", "stopped")  # Значення за замовчуванням, якщо статус відсутній
            running_programs[name] = {"pid": pids, "status": status}

        with open('running_programs.json', 'w', encoding='utf-8') as file:
            json.dump(running_programs, file, ensure_ascii=False, indent=4)
    

    def check_autorestart(self):
        try:
            for program_name, pids in self.processes.items():
                if "autorestart" in self.programs[program_name].get("attributes", []):
                    for pid in pids:
                        if not psutil.pid_exists(pid):
                            self.logger.info(f"Program '{program_name}' was closed from outside, restart...")
                            self.launch_program(program_name)

            self.root.after(5000, self.check_autorestart)
        except Exception as e:
            self.logger.info(f" {e} error func check_autorestart ")

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
                self.stats_dir = config.get('stats_dir', 'stats')
                self.launcher_additional_notify = config.get('launcher_additional_notify', 'False').lower() == 'true'
                self.restart_script_file_name = config.get('restart_script_file_name', 'restart.pyw')
                self.text_color = config.get('text_color', '#FFFFFF')
                self.app_geometry = config.get('app_geometry', '600x400')
                self.launcher_version = config.get('launcher_version', '00000000000000')
                self.attributes = config.get('attributes', {})
                self.app_map = config.get('app_map', {})
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
                self.categories = config.get('categories', '[]')
                self.filter_attribute = config.get('filter_attribute', '')
                self.colors = config.get('colors', '[]')
                self.circle_color = config.get('circle_color', 'black')
                self.circle_color = config.get('circle_color', 'white')
                self.white_list = config.get('white_list', '')
                self.lang = config.get('lang', 'en')
                self.additional_processes = config.get('additional_processes', [])
                self.name_check_interval = config.get('name_check_interval', 20)
                
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
        add_window = tk.Toplevel(self.main_frame)
        add_window.title(self.loc._("Add Program"))
        add_window.iconbitmap("icon.ico")
        add_window.configure(bg=self.color_code)

        program_name_var = tk.StringVar()
        program_path_var = tk.StringVar()
        command_var = tk.StringVar()
        attributes_var = tk.StringVar()
        category_var = tk.StringVar()
        description_var = tk.StringVar()
        self_console_var = tk.BooleanVar()

        # Grid layout for alignment
        for i in range(7):  # for 7 rows of data entry
            add_window.grid_rowconfigure(i, pad=5)
            add_window.grid_columnconfigure(0, minsize=150)

        # Program Name
        tk.Label(add_window, text=self.loc._("program_name"), anchor="e", bg=self.color_code).grid(row=0, column=0, sticky="e")
        tk.Entry(add_window, textvariable=program_name_var, bg=self.color_code).grid(row=0, column=1, sticky="ew")

        # Program Path
        tk.Label(add_window, text=self.loc._("program_path2"), anchor="e", bg=self.color_code).grid(row=1, column=0, sticky="e")
        path_frame = tk.Frame(add_window, bg=self.color_code)
        tk.Entry(path_frame, textvariable=program_path_var, width=30, bg=self.color_code).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(path_frame, text="...", command=lambda: update_program_path(), bg=self.color_code).pack(side=tk.LEFT)
        path_frame.grid(row=1, column=1, sticky="ew")

        # Command for Launch
        tk.Label(add_window, text=self.loc._("command_for_launch"), anchor="e", bg=self.color_code).grid(row=2, column=0, sticky="e")
        tk.Entry(add_window, textvariable=command_var, bg=self.color_code).grid(row=2, column=1, sticky="ew")

        # Attributes
        tk.Label(add_window, text=self.loc._("attributes_title"), anchor="e", bg=self.color_code).grid(row=3, column=0, sticky="e")
        tk.Entry(add_window, textvariable=attributes_var, bg=self.color_code).grid(row=3, column=1, sticky="ew")

        # Category
        tk.Label(add_window, text=self.loc._("category"), anchor="e", bg=self.color_code).grid(row=4, column=0, sticky="e")
        tk.Entry(add_window, textvariable=category_var, bg=self.color_code).grid(row=4, column=1, sticky="ew")

        # Description
        tk.Label(add_window, text=self.loc._("program_description"), anchor="e", bg=self.color_code).grid(row=5, column=0, sticky="e")
        description_entry = tk.Text(add_window, height=5, width=30, bg=self.color_code)
        description_entry.grid(row=5, column=1, sticky="nsew")
        description_entry.insert(tk.END, description_var.get())

        # Checkbox for New Console
        tk.Checkbutton(add_window, text=self.loc._("launch_with_new_console"), variable=self_console_var, bg=self.color_code).grid(row=6, column=0, columnspan=2, sticky="w", padx=5)

        def update_program_path():
            selected_path = filedialog.askopenfilename(title=self.loc._("select_program"))
            if selected_path:
                program_path_var.set(selected_path)
                if not command_var.get():
                    command_var.set(selected_path)

        def save_program():
            name = program_name_var.get()
            path = program_path_var.get()
            command = command_var.get() or path  # Use path if command is empty
            attributes = attributes_var.get().split(',') + [category_var.get()] if category_var.get() else attributes_var.get().split(',')
            attributes = [attr.strip() for attr in attributes if attr]
            description = description_entry.get("1.0", tk.END).strip()

            if name and path:
                self.programs[name] = {
                    "path": path,
                    "command": command,
                    "close_command": "",
                    "launch_count": 0,
                    "total_runtime": 0.0,
                    "description": description,
                    "self_console": "True" if self_console_var.get() else "False",
                    "attributes": attributes
                }
                self.save_programs()
                self.refresh_program_list()
                add_window.destroy()

        # Buttons
        tk.Button(add_window, text=self.loc._("save"), command=save_program, bg=self.color_code).grid(row=7, column=0, columnspan=2, pady=10)
        tk.Button(add_window, text=self.loc._("cancel"), command=add_window.destroy, bg=self.color_code).grid(row=8, column=0, columnspan=2, pady=5)

        # Configure column resizing
        add_window.grid_columnconfigure(1, weight=1)  # Allow the entry fields to expand
        add_window.update_idletasks()  # Ensure all widgets are rendered before resizing

        # Adjust window size to fit content
        add_window.geometry(f"{add_window.winfo_reqwidth()}x{add_window.winfo_reqheight()}")



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
        if self.dev_mode:
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
                self.save_running_programs()
                self.save_stats(program_name, {"event": "start","timestamp": time.time(),"pid": pid})
                self.logger.info(f"Program '{program_name}' launched with the command: {command}")
                self.save_programs()
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
            search_term = self.search_var.get().strip() if self.search_var else ""

            # Перевіряємо, чи пошуковий термін є командою
            if search_term.startswith("!") and search_term.endswith("!") and len(search_term) > 1:
                # Видаляємо `!` з початку і кінця, очищаємо пробіли
                command = search_term[1:-1].strip()
                self.execute_launcher_command(command)
                
                # Очищаємо рядок пошуку
                self.search_var.set("")
                return  # Завершуємо функцію, оскільки команда вже виконана

            # Звичайна логіка пошуку
            search_term = search_term.lower()
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
            self.load_running_programs()

            # Якщо є відфільтровані програми, оновлюємо список
            if filtered_programs:
                # Оновлюємо відображення програми в Listbox
                self.refresh_program_list(filtered_programs)
            else:
                # Якщо немає збігів, не відображаємо програми або виводимо повідомлення
                self.listbox.delete(0, tk.END)  # Очищаємо список
                self.listbox.insert(tk.END, self.loc._("search_not_found"))  # Повідомлення про відсутність збігів

    def save_stats(self, program_name, data):
        """Зберігає статистику в JSON-файл для конкретної програми."""
        file_path = os.path.join(self.stats_dir, f"{program_name}.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                existing_data = json.load(f)
        else:
            existing_data = []

        existing_data.append(data)

        with open(file_path, "w") as f:
            json.dump(existing_data, f, indent=4)
    
    def close_program(self):
        if not self.protect_mode:
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
                                    
                                    self.save_stats(program_name, {"event": "stop","timestamp": time.time(),"pid": pid,"runtime": elapsed_time})

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
            status = program_info.get("status", "stopped")  # Брати статус зі словника
            color = self.status_colors.get(status, self.text_color)

            # Перевірка статусу в self.processes
            if program_name in self.processes:
                process_status = self.processes[program_name]  # Отримати статус з self.processes

                # Якщо process_status є списком, перевіряємо чи він порожній
                if isinstance(process_status, list) and process_status:
                    process_status = process_status[0]  # Вибираємо перший елемент
                else:
                    process_status = "stopped"  # Якщо список порожній або не список, встановлюємо "stopped"

                # Якщо статус є в self.status_colors, вибираємо відповідний колір
                color = self.status_colors.get(process_status, self.text_color)

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
        try:
            if os.path.exists('running_programs.json'):
                with open('running_programs.json', 'r', encoding='utf-8') as file:
                    running_programs = json.load(file)
        except Exception as e:
                print(e)
        # Оновлення статусу у running_programs
        if program_name not in running_programs:
            running_programs[program_name] = {}

        # Запис нового статусу і PID
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
        self.running_programs = running_programs
    
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
        if self.displays_datails_panel:
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
        if self.displays_datails_panel:
            self.displays_datails_panel = False
        else:
            self.displays_datails_panel = True
            
            
    def updata_panell(self):
        if self.displays_datails_panel:
            program_details = self.program_details
            program_details = self.program_details + f"\n\nCPU: {round(self.monitor.get_cpu_load(), 0)}%,\nMemory usage: {round(self.monitor.get_memory_usage(), 0)}%\n\n"
            self.details_label.config(width= 30, text=program_details, fg = self.text_color)
            self.root.after(800, self.updata_panell)

    def edit_program(self):
        selected = self.listbox.curselection()
        if not selected or len(selected) > 1:
            return

        listbox_entry = self.listbox.get(selected[0])
        program_name = listbox_entry.split(" (")[0]

        if program_name not in self.programs:
            return

        # Get current program details
        current_program = self.programs[program_name]

        # Create edit window
        edit_window = tk.Toplevel(self.main_frame)
        edit_window.title(self.loc._("Edit Program"))
        edit_window.iconbitmap("icon.ico")
        edit_window.configure(bg=self.color_code)

        program_name_var = tk.StringVar(value=program_name)
        program_path_var = tk.StringVar(value=current_program.get("path", ""))
        command_var = tk.StringVar(value=current_program.get("command", ""))
        attributes_var = tk.StringVar(value=", ".join(current_program.get("attributes", [])))
        category_var = tk.StringVar()
        description_var = tk.StringVar()
        self_console_var = tk.BooleanVar(value=current_program.get("self_console", "False") == "True")

        # Extract category if exists in attributes
        if current_program.get("attributes"):
            category_var.set(current_program["attributes"][-1])
            attributes_var.set(", ".join(current_program["attributes"][:-1]))

        # Grid layout for alignment
        for i in range(7):
            edit_window.grid_rowconfigure(i, pad=5)
            edit_window.grid_columnconfigure(0, minsize=150)

        # Program Name
        tk.Label(edit_window, text=self.loc._("program_name"), anchor="e", bg=self.color_code).grid(row=0, column=0, sticky="e")
        tk.Entry(edit_window, textvariable=program_name_var, bg=self.color_code).grid(row=0, column=1, sticky="ew")

        # Program Path
        tk.Label(edit_window, text=self.loc._("program_path2"), anchor="e", bg=self.color_code).grid(row=1, column=0, sticky="e")
        path_frame = tk.Frame(edit_window, bg=self.color_code)
        tk.Entry(path_frame, textvariable=program_path_var, width=30, bg=self.color_code).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(path_frame, text="...", command=lambda: update_program_path(), bg=self.color_code).pack(side=tk.LEFT)
        path_frame.grid(row=1, column=1, sticky="ew")

        # Command for Launch
        tk.Label(edit_window, text=self.loc._("command_for_launch"), anchor="e", bg=self.color_code).grid(row=2, column=0, sticky="e")
        tk.Entry(edit_window, textvariable=command_var, bg=self.color_code).grid(row=2, column=1, sticky="ew")

        # Attributes
        tk.Label(edit_window, text=self.loc._("attributes_title"), anchor="e", bg=self.color_code).grid(row=3, column=0, sticky="e")
        tk.Entry(edit_window, textvariable=attributes_var, bg=self.color_code).grid(row=3, column=1, sticky="ew")

        # Category
        tk.Label(edit_window, text=self.loc._("category"), anchor="e", bg=self.color_code).grid(row=4, column=0, sticky="e")
        tk.Entry(edit_window, textvariable=category_var, bg=self.color_code).grid(row=4, column=1, sticky="ew")

        # Description
        tk.Label(edit_window, text=self.loc._("program_description"), anchor="e", bg=self.color_code).grid(row=5, column=0, sticky="e")
        description_entry = tk.Text(edit_window, height=5, width=30, bg=self.color_code)
        description_entry.grid(row=5, column=1, sticky="nsew")
        description_entry.insert(tk.END, current_program.get("description", ""))

        # Checkbox for New Console
        tk.Checkbutton(edit_window, text=self.loc._("launch_with_new_console"), variable=self_console_var, bg=self.color_code).grid(row=6, column=0, columnspan=2, sticky="w", padx=5)

        def update_program_path():
            selected_path = filedialog.askopenfilename(title=self.loc._("select_program"))
            if selected_path:
                program_path_var.set(selected_path)
                if not command_var.get():
                    command_var.set(selected_path)

        def save_changes():
            new_name = program_name_var.get()
            path = program_path_var.get()
            command = command_var.get() or path
            attributes = attributes_var.get().split(',') + [category_var.get()] if category_var.get() else attributes_var.get().split(',')
            attributes = [attr.strip() for attr in attributes if attr]
            description = description_entry.get("1.0", tk.END).strip()

            if new_name and path:
                # Зберігаємо стару позицію програми
                old_position = None
                for index, (name, _) in enumerate(self.programs.items()):
                    if name == program_name:
                        old_position = index
                        break
                
                # Видаляємо стару програму з self.programs
                self.programs.pop(program_name)

                # Додаємо нову програму
                self.programs[new_name] = {
                    "path": path,
                    "command": command,
                    "close_command": "",
                    "launch_count": current_program.get("launch_count", 0),
                    "total_runtime": current_program.get("total_runtime", 0.0),
                    "description": description,
                    "self_console": "True" if self_console_var.get() else "False",
                    "attributes": attributes
                }

                # Оновлюємо порядок
                program_order = [name for name in self.programs.keys()]
                if old_position is not None:
                    program_order.insert(old_position, program_order.pop())

                # Створюємо новий словник, зберігаючи порядок
                self.programs = {key: self.programs[key] for key in program_order}

                # Зберігаємо зміни
                self.save_programs()
                self.refresh_program_list()
                edit_window.destroy()

        # Buttons
        tk.Button(edit_window, text=self.loc._("save"), command=save_changes, bg=self.color_code).grid(row=7, column=0, columnspan=2, pady=10)
        tk.Button(edit_window, text=self.loc._("cancel"), command=edit_window.destroy, bg=self.color_code).grid(row=8, column=0, columnspan=2, pady=5)

        # Configure column resizing
        edit_window.grid_columnconfigure(1, weight=1)
        edit_window.update_idletasks()

        # Adjust window size to fit content
        edit_window.geometry(f"{edit_window.winfo_reqwidth()}x{edit_window.winfo_reqheight()}")


    
    def hide_window(self):
        self.root.withdraw()
        
    def show_window(self):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
            self.root.focus_force()
            self.root.lift()  # Робить вікно активним
            self.root.attributes('-topmost', True)  # Поверх інших вікон
            self.root.attributes('-topmost', False)  # Скасовує завжди "поверх інших"
            self.root.focus_force()  # Примусово переводить фокус на вікно
            
    def toggle_visibility_window(self):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
        else:
            self.root.withdraw()
    
    
    def forcibly_delete_program(self):
        selected = self.listbox.curselection()
        if selected:
            if len(selected) > 1:
                return

            listbox_entry = self.listbox.get(selected[0])
            program_name = listbox_entry.split(" (")[0]

            # Перевірка на наявність атрибута 'sys'

            # Діалогове вікно підтвердження
            confirm = messagebox.askyesno(self.loc._("confirmation_title"), self.loc._("confirmation_message").format(program_name=program_name))
            if confirm:
                del self.programs[program_name]
                self.save_programs()
                self.refresh_program_list()
    
    def delete_program(self):
        if not self.protect_mode:
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
        """Перевіряє статус всіх програм та оновлює їх, якщо потрібно."""
        for program_name, pids in list(self.processes.items()):
            for pid in pids:
                # Перевіряємо наявність процесу
                if psutil.pid_exists(pid):
                    # Якщо процес існує, статус "runn"
                    current_status = "runn"
                else:
                    # Якщо процес не існує, статус "stopped"
                    current_status = "stopped"
                    self.processes[program_name].remove(pid)
                    start_time = self.start_times.pop(pid, None)
                    if start_time:
                        elapsed_time = time.time() - start_time
                        self.programs[program_name]["total_runtime"] += elapsed_time
                        # Логування завершення програми
                        self.logger.info(f"Програма '{program_name}' (PID: {pid}) завершена через {elapsed_time:.2f} секунд")
                        self.save_stats(program_name, {
                            "event": "stop",
                            "timestamp": time.time(),
                            "pid": pid,
                            "runtime": elapsed_time
                        })
                
                # Оновлення статусу програми в running_programs
                current_program_status = self.running_programs.get(program_name, {}).get('status', 'stopped')

                # Якщо поточний статус програми "runn" або "stopped" (не користувацький), перевіряємо наявність процесу
                if current_program_status not in ["runn", "stopped"]:
                    # Якщо статус інший, це користувацький статус і він пріоритетний
                    self.update_status(program_name, current_program_status)
                elif current_status == "runn" and current_program_status == "stopped":
                    # Якщо процес існує, а статус був stopped, змінюємо на running
                    self.update_status(program_name, "runn")
                elif current_status == "stopped" and current_program_status == "runn":
                    # Якщо процес не існує, а статус був running, змінюємо на stopped
                    self.update_status(program_name, "stopped")
                
            # Збереження статусів після перевірки всіх програм
            self.save_running_programs()

        # Перевірка кожні 2 секунди
        self.root.after(2000, self.check_programs_status)


    def show_version_info(self):
        messagebox.showinfo(
                        self.loc._("version"),
                        self.loc._("program_version").format(version=self.launcher_version),
                    )
                    
    def process_tree_viewer(self):
        self.error_frame = None
        self.info_window_live = True
        self.process_is_live = True
        """Функція для отримання і показу інформації про вибраний процес"""
        selected = self.listbox.curselection()
        if selected:
            # Отримуємо ім'я програми, видаляючи частину з PID
            program_names = [self.listbox.get(i).split(" (")[0] for i in selected]
            program_name = program_names[0]  # Якщо вибрано тільки один елемент

            # Визначаємо PID для вибраного процесу
            if program_name in self.processes:
                pid_list = self.processes[program_name]

                if not pid_list:
                    self.show_error(f"Не знайдено процесів для {program_name}.")
                    return

                # Створюємо нове вікно для відображення процесу
                if self.info_window:
                    self.info_window.destroy()  # Закриваємо попереднє вікно, якщо воно є

                self.info_window = tk.Toplevel(self.root)
                self.info_window.title(f"Info about {program_name}")
                self.info_window.geometry("600x400")
                self.info_window.config(bg=self.color_code)  # Встановлюємо фон

                # Створюємо дерево для відображення процесів
                self.treeview = ttk.Treeview(
                    self.info_window,
                    columns=("Name", "PID", "CPU", "Memory", "Status", "Operation"),
                    show="headings"
                )
                self.treeview.pack(fill=tk.BOTH, expand=True)

                # Налаштування заголовків для дерева
                self.treeview.heading("Name", text="Name")
                self.treeview.heading("PID", text="PID")
                self.treeview.heading("CPU", text="CPU")
                self.treeview.heading("Memory", text="Memory")
                self.treeview.heading("Status", text="Status")
                self.treeview.heading("Operation", text="Operation")

                # Налаштування стилю Treeview
                style = ttk.Style()
                style.configure("Custom.Treeview", 
                                background=self.color_code,  # Колір фону елементів
                                foreground="black",  # Колір тексту
                                rowheight=25,        # Висота рядків
                                fieldbackground=self.color_code)  # Колір фону порожніх областей
                style.configure("Custom.Treeview.Heading",
                                background=self.color_code,  # Колір заголовків
                                foreground="black",  # Колір тексту заголовків
                                font=("Arial", 10, "bold"))
                style.map("Custom.Treeview", 
                          background=[("selected", "#a688ff")],  # Колір виділення
                          foreground=[("selected", "white")])

                self.treeview.configure(style="Custom.Treeview")

                # Запускаємо окремий потік для отримання інформації про процес
                threading.Thread(target=self.load_process_info, args=(pid_list[0], program_name), daemon=True).start()

                # Оновлюємо інформацію про процес кожну секунду тільки для відкритого вікна
                self.update_processes()

        else:
            self.show_error("Будь ласка, виберіть процес з списку.")

    def load_process_info(self, pid, program_name):
        """Збирає і відображає інформацію про процес у окремому потоці"""
        try:
            # Шукаємо процес за PID
            process = psutil.Process(pid)

            # Отримуємо інформацію про процес
            name = process.name()
            cpu = f"{process.cpu_percent(interval=0.1):.2f}%"
            memory = f"{process.memory_info().rss / (1024 * 1024):.2f} MB"
            status = process.status()
            operation = self.get_process_operation(process)

            # Збираємо дочірні процеси рекурсивно
            children_info = self.get_children_info(process)

            # Оновлюємо інтерфейс в головному потоці
            if self.info_window_live:
                self.root.after(10, self.update_process_info, pid, name, cpu, memory, status, operation, children_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def get_process_operation(self, process):
        """Отримуємо опис операції, яку виконує процес, якщо доступно"""
        try:
            return process.exe()  # Відображає шлях до виконуваного файлу
        except psutil.AccessDenied:
            return "Доступ обмежений"

    def get_children_info(self, process):
        """Отримуємо інформацію про дочірні процеси рекурсивно"""
        children_info = []
        try:
            children = process.children(recursive=True)  # Отримуємо всі дочірні процеси рекурсивно
            for child in children:
                child_info = {
                    "PID": child.pid,
                    "Name": child.name(),
                    "CPU": f"{child.cpu_percent(interval=0.1):.2f}%",
                    "Memory": f"{child.memory_info().rss / (1024 * 1024):.2f} MB",
                    "Status": child.status(),
                    "Operation": self.get_process_operation(child)
                }
                children_info.append(child_info)
        except psutil.AccessDenied:
            children_info.append("Доступ до дочірніх процесів обмежений.")
        return children_info

    def update_process_info(self, pid, name, cpu, memory, status, operation, children_info):
        """Оновлює інформацію у вікні"""
        try:
            if self.info_window_live:
                if not self.info_window or not self.treeview:
                    return  # Вихід, якщо вікно або treeview було закрито

                # Очищаємо Treeview перед оновленням
                if self.info_window_live:
                    try:
                        for item in self.treeview.get_children():
                            self.treeview.delete(item)
                    except:
                        self.info_window_live = False

                # Додаємо інформацію про основний процес (чорний)
                if self.info_window_live:
                    self.treeview.insert("", "end", text=name, values=(name, pid, cpu, memory, status, operation), tags=("main_process"))

                # Додаємо інформацію про дочірні процеси (жовтий)
                if self.info_window_live:
                    for child_info in children_info:
                        self.treeview.insert("", "end", text=child_info["Name"], values=(child_info["Name"], child_info["PID"], child_info["CPU"], child_info["Memory"], child_info["Status"], child_info["Operation"]), tags=("child_process"))

                # Додаємо кольорові теги для виділення процесів
                self.treeview.tag_configure("main_process", foreground="black")
                self.treeview.tag_configure("child_process", foreground="yellow")
                
                # Додаємо кольорові теги для дочірніх дочірніх процесів (синій)
        except:
            self.info_window_live = False
    def update_processes(self):
        """Оновлює інформацію про процеси кожну секунду"""
        if self.info_window:  # Оновлення інформації тільки якщо вікно перегляду відкрито
            selected = self.listbox.curselection()
            if selected:
                program_names = [self.listbox.get(i).split(" (")[0] for i in selected]
                program_name = program_names[0]
                if program_name in self.processes:
                    pid_list = self.processes[program_name]

                    if not pid_list:
                            self.show_error(f"Не знайдено процесів для {program_name}.")
                            self.process_is_live = False
                            pass
                    try:
                        if self.process_is_live:
                            threading.Thread(target=self.load_process_info, args=(pid_list[0], program_name), daemon=True).start()
                    except:
                        self.process_is_live = False
                        self.show_error("Процес відсутній")
                        
            # Оновлюємо інформацію кожну секунду, тільки якщо вікно відкрито
            if self.info_window_live and self.process_is_live:
                self.root.after(1000, self.update_processes)

    def show_error(self, message):
        """Показує повідомлення про помилку в основному вікні, очищаючи попередні"""
        if self.info_window_live and self.info_window:
            try:
                # Якщо контейнер для помилок не створено, створимо його
                if not self.error_frame:
                    self.error_frame = tk.Frame(self.info_window, bg=self.color_code)
                    self.error_frame.pack(fill=tk.X)

                # Очищаємо попередні повідомлення про помилки
                for widget in self.error_frame.winfo_children():
                    widget.destroy()

                # Додаємо нове повідомлення про помилку
                error_label = tk.Label(self.error_frame, text=message, foreground="red", bg=self.color_code)
                error_label.pack(anchor="w", padx=10, pady=5)

            except Exception as e:
                print(f"Помилка при відображенні повідомлення: {e}")
                self.info_window_live = False


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
        # Верхнє меню
        menubar = Menu(self.root, bg="#f7f7f7", fg="black", font=("Arial", 10))

        # Вкладка "Файл"
        if self.file_menu_:
            file_menu = Menu(menubar, tearoff=1, bg="#f7f7f7", fg="black", font=("Arial", 9))
            file_menu.add_command(label=self.loc._("add_program"), command=self.add_program)
            file_menu.add_command(label=self.loc._("clear_cache_file"), command=self.clear_running_programs)
            file_menu.add_command(label=self.loc._("open_script_folder"), command=self.open_script_folder)
            file_menu.add_command(label=self.loc._("check_program"), command=lambda: self.check_executables(first_run=False, in_cycle=False))
            menubar.add_cascade(label=self.loc._("file"), menu=file_menu)

        # Вкладка "Інтерфейс"
        if self.interface_meny_:
            interface_menu = Menu(menubar, tearoff=1, bg="#f7f7f7", fg="black", font=("Arial", 9))
            interface_menu.add_command(label=self.loc._("change_interface_color"), command=self.choose_color)
            interface_menu.add_command(label=self.loc._("change_text_color"), command=self.choose_text_color)
            interface_menu.add_command(label=self.loc._("save_color_to_config"), command=self.save_color_to_config)
            interface_menu.add_command(label=self.loc._("save_text_color_to_config"), command=self.save_text_color_to_config)
            if self.add_hide_details_panel_btn:
                interface_menu.add_command(label=self.loc._("hide_details_panel"), command=self.hide_details_panel)
            menubar.add_cascade(label=self.loc._("interface"), menu=interface_menu)
        
        
        mode_menu = Menu(menubar, tearoff=1, bg="#f7f7f7", fg="black", font=("Arial", 9))
        mode_menu.add_command(label=self.loc._("mode_blue"), command=self.trigger_bsod)
        mode_menu.add_command(label=self.loc._("mode_winter_in_germany"), command=lambda: self.call_program("flakes"))
        mode_menu.add_command(label=self.loc._("console"), command=self.create_console_window)
        menubar.add_cascade(label=self.loc._("mode_menu"), menu=mode_menu)
        
        # Вкладка "Категорії"
        self.category_menu = Menu(menubar, tearoff=1)
        menubar.add_cascade(label=self.loc._("category"), menu=self.category_menu)

        # Вкладка "Програми"
        programs_menu = Menu(menubar, tearoff=1, bg="#f7f7f7", fg="black", font=("Arial", 9))
        programs_menu.add_command(label=self.loc._("reload_programs_list"), command=self.load_programs_and_refresh)
        programs_menu.add_command(label=self.loc._("show_hidden_programs"), command=self.toggle_hidden_programs)
        programs_menu.add_command(label=self.loc._("program_manager"), command=lambda: self.call_program("manager"))
        programs_menu.add_command(label=self.loc._("move_btn"), command=self.create_move_buttons)
        programs_menu.add_command(label=self.loc._("version_info"), command=self.show_version_info)
        menubar.add_cascade(label=self.loc._("programs-menu"), menu=programs_menu)

        # Вкладка "Інструменти"
        tools_menu = Menu(menubar, tearoff=1, bg="#f7f7f7", fg="black", font=("Arial", 9))
        tools_menu.add_command(label=self.loc._("toggle_console_visibility"), command=self.toggle_console_visibility)
        tools_menu.add_command(label=self.loc._("call_processes_window"), command=self.display_process_list)
        tools_menu.add_command(label=self.loc._("restart_launcher"), command=self.restart_script)
        tools_menu.add_command(label=self.loc._("recconect_client"), command=self.recconect)
        tools_menu.add_command(label=self.loc._("kill_all_launcher_additional_proces"), command=lambda: self.call_program("killer"))
        menubar.add_cascade(label=self.loc._("tools"), menu=tools_menu)

        # Вкладка "Вихід"
        exit_menu = Menu(menubar, tearoff=1, bg="#f7f7f7", fg="black", font=("Arial", 9))
        exit_menu.add_command(label=self.loc._("exit"), command=self.exit_app_from_menu)
        exit_menu.add_command(label=self.loc._("exit_pc"), command=lambda: subprocess.Popen("shutdown /s /t 0"))
        menubar.add_cascade(label=self.loc._("exit"), menu=exit_menu)
        
        # Застосування меню до вікна
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
            scrollbar = tk.Scrollbar(frame, command=self.listbox.yview, troughcolor=self.color_code, bg=self.color_code, activebackground=self.color_code, width=1, relief="flat")
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
            self.context_menu.add_command(label=self.loc._("show_info"), command=self.process_tree_viewer)
            self.context_menu.add_command(label=self.loc._("open_file_location"), command=self.open_file_location)

        # Оновлення списку програм
        self.refresh_program_list()
        self.check_programs_status()
    
    def move_up(self):
        try:
            index = self.listbox.curselection()[0]
        except IndexError:
            return

        if index > 0:
            # Отримуємо елементи як список
            items = list(self.programs.items())
            
            # Змінюємо місцями елементи
            items[index], items[index - 1] = items[index - 1], items[index]

            # Перетворюємо назад у словник
            self.programs = {str(k): v for k, v in items}

            # Зберігаємо та оновлюємо інтерфейс
            self.save_programs()
            self.refresh_program_list()

            # Залишаємо виділення
            self.listbox.select_set(index - 1)
            self.listbox.activate(index - 1)

    def move_down(self):
        try:
            index = self.listbox.curselection()[0]
        except IndexError:
            return

        if index < len(self.programs) - 1:
            # Отримуємо елементи як список
            items = list(self.programs.items())

            # Змінюємо місцями елементи
            items[index], items[index + 1] = items[index + 1], items[index]

            # Перетворюємо назад у словник
            self.programs = {str(k): v for k, v in items}

            # Зберігаємо та оновлюємо інтерфейс
            self.save_programs()
            self.refresh_program_list()

            # Залишаємо виділення
            self.listbox.select_set(index + 1)
            self.listbox.activate(index + 1)

    def create_move_buttons(self):
        """
        Створює кнопки для переміщення програм вгору і вниз, розташовані під основним інтерфейсом.
        """
        self.hide_details_panel()
        self.displays_datails_panel = False
        # Якщо кнопки вже існують, видаляємо старі, щоб створити нові
        if hasattr(self, "buttons_frame") and self.buttons_frame.winfo_exists():
            self.destroy_move_buttons()

        # Створюємо контейнер для кнопок
        self.buttons_frame = tk.Frame(self.main_frame, bg=self.color_code)
        self.buttons_frame.pack(side=tk.TOP, pady=2, fill=tk.X)

        # Кнопка для переміщення програми вгору
        self.move_up_button = tk.Button(self.buttons_frame, text=self.loc._("move_up"), command=self.move_up, bg=self.color_code)
        self.move_up_button.pack(side=tk.BOTTOM, padx=2)

        # Кнопка для переміщення програми вниз
        self.move_down_button = tk.Button(self.buttons_frame, text=self.loc._("move_down"), command=self.move_down, bg=self.color_code)
        self.move_down_button.pack(side=tk.BOTTOM, padx=2)

        # Кнопка для знищення кнопок
        self.destroy_buttons_button = tk.Button(self.buttons_frame, text=self.loc._("destroy_buttons"), command=self.destroy_move_buttons, bg=self.color_code)
        self.destroy_buttons_button.pack(side=tk.LEFT, padx=2)

    def destroy_move_buttons(self):
        """
        Знищує кнопки для переміщення програм.
        """
        if hasattr(self, "buttons_frame") and self.buttons_frame.winfo_exists():
            self.buttons_frame.destroy()
        self.hide_details_panel()

        
        
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
            pass

      
      
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
            pass
        

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
    
    def generate_circle_with_quarters(self):
        # Create a blank image with transparency
        size = 200
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Define colors for each quarter
        #colors = ["red", "cyan", "blue", "green"]
        #colors = ["blue", "cyan", "#9e2680", "red", "white"]
        # Define the center and radius of the circle
        center = size // 2
        radius = center

        # Draw each quarter using pieslice
        angles = [(0, 90), (90, 180), (180, 270), (270, 360)]
        for i, angle in enumerate(angles):
            # Adjust bounds for top quarters to shift 1 pixel to the left
            bounds = [(0, 0), (size, size)]
            if angle[0] < 180:  # Top quarters
                bounds = [(-1, 0), (size - 1, size)]
            draw.pieslice(bounds, start=angle[0], end=angle[1], fill=self.colors[i])

        # Draw central circle filled with white
        inner_size = 80
        inner_bounds = [
            (center - inner_size // 2, center - inner_size // 2),
            (center + inner_size // 2, center + inner_size // 2)
        ]
        draw.ellipse(inner_bounds, fill=self.circle_color)

        # Draw gray radial lines from center to edges (up, down, left, right)
        line_color = "gray"
        directions = [(0, -radius), (0, radius), (-radius, 0), (radius, 0)]
        for dx, dy in directions:
            x = center + dx
            y = center + dy
            draw.line([(center, center), (x, y)], fill=line_color, width=1)

        # Add edge smoothing using anti-aliasing
        smooth_image = image.resize((size * 4, size * 4), Image.Resampling.LANCZOS)
        image = smooth_image.resize((size, size), Image.Resampling.LANCZOS)
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
        self.icon = Icon(self.loc._("app_title_tray"), self.generate_circle_with_quarters(), self.loc._("app_title_tray"), menu)
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
    
    
    def trigger_bsod(self):
        if self.protect_mode:
            # Отримуємо привілейні права для виклику BSOD
            ctypes.windll.ntdll.RtlAdjustPrivilege(19, True, False, ctypes.byref(ctypes.c_bool()))
            # Викликаємо критичний BSOD через ініціювання помилки системи
            ctypes.windll.ntdll.NtRaiseHardError(0xC000007B, 0, 0, 0, 6, ctypes.byref(ctypes.c_ulong()))


    
    def restart_script(self):
        """
        Знаходить шлях до першого скрипта і передає його другому скрипту для запуску.
        """
        # Знаходимо шлях до поточного скрипта
        script_path = os.path.realpath(sys.argv[0])  # Повний шлях до першого скрипта
        second_script_path = os.path.join(os.path.dirname(script_path), self.restart_script_file_name)  # Шлях до другого скрипта

        if os.path.exists(second_script_path):
            subprocess.Popen([sys.executable, second_script_path, script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.exit_app_from_menu()
        else:
            print("Не знайдено другого скрипта!")    
    
if __name__ == "__main__":
    root = tk.Tk()
    app = AppLauncher(root)
    root.mainloop()
