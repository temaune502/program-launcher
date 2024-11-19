import subprocess
import json
import os
import time

def load_programs_from_file(config_file):
    """
    Завантажує список програм із файлу налаштувань.
    
    :param config_file: Шлях до JSON файлу налаштувань.
    :return: Список програм із їх параметрами.
    """
    with open(config_file, 'r') as file:
        programs = json.load(file)
    return programs

def run_programs_in_sequence(programs):
    """
    Запускає програми вказані у списку з затримкою між запуском кожної наступної.
    
    :param programs: Список словників із шляхами, робочими каталогами, аргументами для запуску програм і параметром видимості вікна.
    """
    for program in programs:
        path = program.get("path")
        cwd = program.get("working_directory")
        arguments = program.get("arguments", "")
        hidden = program.get("hidden", False)  # True для прихованого запуску
        delay = program.get("delay", 0)  # Затримка перед запуском (у секундах)
        
        if not path or not os.path.exists(path):
            print(f"Програма '{path}' не знайдена.")
            continue
        
        try:
            # Формуємо команду для запуску з аргументами
            command = f'"{path}" {arguments}'
            
            # Встановлюємо параметри для прихованого або видимого вікна
            startupinfo = subprocess.STARTUPINFO()
            creationflags = subprocess.CREATE_NEW_CONSOLE
            if hidden:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Запускаємо програму
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            print(f"Програма '{path}' запущена з затримкою {delay} секунд.")
            
            # Затримка перед запуском наступної програми
            time.sleep(delay)
        
        except Exception as e:
            print(f"Помилка під час запуску програми '{path}': {e}")

# Шлях до файлу налаштувань
config_file = "config.json"

# Завантажуємо програми та запускаємо їх
programs_to_run = load_programs_from_file(config_file)
run_programs_in_sequence(programs_to_run)
