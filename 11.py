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
from PIL import Image, ImageDraw, ImageGrab
import threading
from datetime import datetime
import ctypes
import sys

class AppLauncher:
    def __init__(self, root):
        self.root = root
        self.color_code = "#FFFFFF"
        self.attributes = {}
        self.load_config()
        self.log_file = "launcher.log"
        self.programs = {}
        self.processes = {}
        self.start_times = {}
        self.setup_logging()
        self.create_interface()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.load_programs_and_refresh()
        tray_thread = threading.Thread(target=self.run_in_tray, daemon=True)
        tray_thread.start()
        self.kernel32 = ctypes.windll.kernel32
        self.user32 = ctypes.windll.user32
        self.hide_console()
        self.console_window = self.kernel32.GetConsoleWindow()
        self.disable_console_close_button()
        self.with_start_update_background(self.color_code)

        
    def hide_console(self):
        """Приховати вікно консолі"""
        console_window = self.kernel32.GetConsoleWindow()
        if console_window != 0:
            self.user32.ShowWindow(console_window, 0)  # 0 - приховати\
            
    def show_console(self):
        """Відобразити вікно консолі"""
        console_window = self.kernel32.GetConsoleWindow()
        if console_window != 0:
            self.user32.ShowWindow(console_window, 5)  # 5 - показати
    
    def toggle_console_visibility(self):
        """Перемкнути видимість вікна консолі"""
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
        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as file:
                config = json.load(file)
                self.programs_file = config.get('programs_file', 'programs.json')
                self.attributes = config.get('attributes', {})
                self.color_code = config.get('color', '#FFFFFF')  # Завантажуємо колір або задаємо стандартний

    def setup_logging(self):
        self.logger = logging.getLogger("AppLauncher")
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(self.log_file, maxBytes=1000000, backupCount=3)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def add_program(self):
        program_name = simpledialog.askstring("Назва програми", "Введіть назву програми:")
        if program_name:
            program_path = filedialog.askopenfilename(title="Виберіть програму")
            if program_path:
                attributes = simpledialog.askstring("Атрибути", "Введіть атрибути через кому (sys, autorun, test):")
                self.programs[program_name] = {
                    "path": program_path,
                    "command": program_path,
                    "close_command": "",
                    "launch_count": 0,
                    "total_runtime": 0.0,
                    "description": "",
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
    
    def exit_app(self, icon, item):
        self.icon.stop()
        self.root.quit()
    
    def launch_program(self, program_name=None):
        if not program_name:
            selected = self.listbox.curselection()
            if selected:
                listbox_entry = self.listbox.get(selected)
                program_name = listbox_entry.split(" (")[0]

        if program_name:
            program_info = self.programs.get(program_name)
            if not program_info:
                return

            self.apply_attributes(program_info)
            
            command = program_info["command"]
            program_dir = os.path.dirname(program_info["path"])
            try:
                process = subprocess.Popen(command, cwd=program_dir, shell=True)
                pid = process.pid
                if program_name not in self.processes:
                    self.processes[program_name] = []
                self.processes[program_name].append(pid)
                self.start_times[pid] = time.time()
                self.programs[program_name]["launch_count"] += 1
                self.update_status(program_name, "Запущено")
                self.logger.info(f"Програма '{program_name}' запущена з командою: {command}")
                self.save_programs()
            except Exception as e:
                self.update_status(program_name, f"Помилка: {e}")
                self.logger.error(f"Не вдалося запустити програму '{program_name}': {e}")

    def launch_program_manager(self):
        """Запуск вказаної програми"""
        program_path = "ProgramManager.py"
        try:
            subprocess.Popen([program_path], shell=True)
            print(f"Програма {program_path} успішно запущена.")
        except FileNotFoundError:
            print(f"Помилка: Програму {program_path} не знайдено.")
        except Exception as e:
            print(f"Сталася помилка під час запуску програми: {e}")
    

    
    def update_program_list_with_search(self, event):
        search_term = self.search_var.get().lower()
        filtered_programs = {name: info for name, info in self.programs.items() if search_term in name.lower()}
        self.refresh_program_list(filtered_programs)
    
    def close_program(self):
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
                        self.logger.info(f"Програма '{program_name}' (PID: {pid}) завершена через {elapsed_time:.2f} секунд")
                self.processes[program_name] = []
                self.update_status(program_name, "Зупинено")
                self.save_programs()

            # Перевірка на наявність атрибута 'refresh'
                if "refresh" in self.programs[program_name].get("attributes", []):
                    self.logger.info(f"Перезавантаження 'programs.json' після завершення програми '{program_name}'")
                    self.load_programs_and_refresh()

            else:
                self.update_status(program_name, "Не запущено")
                self.logger.info(f"Спроба завершити програму '{program_name}', яка не була запущена")


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
        self.load_programs()
        for program_name, program_info in self.programs.items():
            if "autorun" in program_info.get("attributes", []):
                self.launch_program(program_name)
        self.check_programs_status()

    def refresh_program_list(self, programs=None):
        if programs is None:
            programs = self.programs

        self.listbox.delete(0, tk.END)
        for program, info in programs.items():
        # Перевірка на атрибут 'hide'
            if "hide" in info.get("attributes", []):
                continue

            status = "Запущено" if self.processes.get(program) else "Не запущено"
            color = "green" if status == "Запущено" else "black"
            self.listbox.insert(tk.END, f"{program} ({status})")
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
                    messagebox.showerror("Помилка", "Файл не знайдено.")


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
        selected = self.listbox.curselection()
        if selected:
            listbox_entry = self.listbox.get(selected)
            program_name = listbox_entry.split(" (")[0]
            program_info = self.programs.get(program_name, {})

            if not program_info:
                details = "Інформація про програму не знайдена."
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


    def create_interface(self):
        self.root.title("Program Launcher")
        self.root.geometry("600x400")
        self.root.configure(bg="#043355")

        # Створюємо верхнє меню
        menubar = Menu(self.root)

        # Створюємо вкладку "Файл"
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Додати програму", command=self.add_program)  # Додаємо програму
        file_menu.add_command(label="Відкрити папку скрипта", command=self.open_script_folder)  # Відкрити папку скрипта 
        file_menu.add_command(label="Менеджер програм", command=self.launch_program_manager)
        menubar.add_cascade(label="Файл", menu=file_menu)

        # Створюємо вкладку "Інтерфейс"
        interface = Menu(menubar, tearoff=0)
        interface.add_command(label="Змінити колір інтерфейсу", command=self.choose_color)
        interface.add_command(label="Зберегти значення кольору", command=self.save_color_to_config)
        menubar.add_cascade(label="Інтерфейс", menu=interface)
        # Створюємо вкладку "Додаткове"
        extra_menu = Menu(menubar, tearoff=0)
        extra_menu.add_command(label="Перезавантажити список програм", command=self.load_programs_and_refresh)        # Перезавантажити список програм
        extra_menu.add_command(label="Показати/приховати консоль", command=self.toggle_console_visibility)
        extra_menu.add_command(label="Вийти", command=self.exit_app_from_menu)  # Кнопка для виходу з програми
        menubar.add_cascade(label="Додаткове", menu=extra_menu)
        # Прикріплюємо меню до вікна
        self.root.config(menu=menubar)

        # Пошуковий рядок
        self.create_search_bar()

        frame = tk.Frame(self.root, bg="#FFFFFF")
        frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(frame, bg="#FFFFFF", fg="black")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-1>", self.on_listbox_double_click)
        self.listbox.bind("<Button-3>", self.show_context_menu)
        self.listbox.bind("<ButtonRelease-1>", self.show_program_details)

        scrollbar = tk.Scrollbar(frame, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        self.details_label = tk.Label(frame, bg="#FFFFFF", fg="black", justify=tk.LEFT, anchor="nw", wraplength=300)
        self.details_label.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)

    # Контекстне меню
        self.context_menu = tk.Menu(self.root, tearoff=0)
     
        self.context_menu.add_command(label="Запустити", command=self.launch_program)
        self.context_menu.add_command(label="Зупинити", command=self.close_program)
        self.context_menu.add_command(label="Редагувати", command=self.edit_program)
        self.context_menu.add_command(label="Видалити", command=self.delete_program)
        self.context_menu.add_command(label="Відкрити розташування файлу", command=self.open_file_location) 
        
        self.refresh_program_list()
        self.check_programs_status()
        print(self.programs)
    def create_search_bar(self):
        self.search_var = tk.StringVar()
        self.search_bar = tk.Entry(self.root, textvariable=self.search_var, bg=self.color_code, fg="black")
        self.search_bar.pack(fill=tk.X)
        self.search_bar.bind('<KeyRelease>', self.update_program_list_with_search)

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
        self.root.config(bg=color)
    
    # Оновлення кольору фону пошукового рядка

        self.listbox.config(bg=color)
        self.details_label.config(bg=color)
        self.search_bar.config(bg=color)
        # Оновлення кольору фону і контекстного меню
        self.context_menu.config(bg=color)
        print("color change ")
        print(color)
        # Можна додати аналогічні оновлення для інших елементів інтерфейсу
      
      
    def with_start_update_background(self, color):

        # Оновлення кольору фону головного вікна
        self.root.config(bg=color)

        self.listbox.config(bg=color)
        self.details_label.config(bg=color)
        # Оновлення кольору фону і контекстного меню
        self.context_menu.config(bg=color)

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
            TrayMenuItem('Показати/Приховати', self.toggle_visibility),  # Залишаємо кнопку для відкриття/приховування головного вікна
            TrayMenu.SEPARATOR,  # Розділювач
            TrayMenuItem('Вийти', self.exit_app)  # Кнопка для виходу з програми
        )
        self.icon = Icon("AppLauncher", self.create_image(), "AppLauncher", menu)
    
        self.icon.run()

    def toggle_visibility(self, icon, item):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
        else:
            self.root.withdraw()

    def exit_app(self, icon, item):
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

