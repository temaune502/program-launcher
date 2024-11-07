import os
import subprocess
import psutil
import json
import win32con
import win32api
import win32gui
import time
from ctypes import POINTER, windll, Structure, cast, CFUNCTYPE, c_int, c_uint, c_void_p, c_bool
from comtypes import GUID
from ctypes.wintypes import HANDLE, DWORD

PBT_POWERSETTINGCHANGE = 0x8013

# Визначення GUID для параметрів живлення
GUID_CONSOLE_DISPLAY_STATE = GUID('{6FE69556-704A-47A0-8F24-C28D936FDA47}')

class POWERBROADCAST_SETTING(Structure):
    _fields_ = [("PowerSetting", GUID),
                ("DataLength", DWORD),
                ("Data", DWORD)]

# Змінна для збереження процесу
process = None

def load_settings():
    """Завантаження шляху до програми з файлу settings.json."""
    with open("settings.json", "r") as file:
        settings = json.load(file)
    return settings.get("program_path")

def start_program(path):
    global process
    if process and process.poll() is None:
        print("Програма вже запущена")
        return
    # Перехід до робочої директорії програми
    program_dir = os.path.dirname(path)
    os.chdir(program_dir)
    print(f"Запускаємо програму: {path}")
    process = subprocess.Popen(path, shell=True)

def kill_process_and_children(pid):
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):  # Отримуємо всіх дочірніх процесів
            child.terminate()  # Надсилаємо сигнал завершення
        parent.terminate()  # Завершуємо основний процес
        gone, still_alive = psutil.wait_procs([parent] + parent.children(recursive=True), timeout=5)
        for p in still_alive:  # У разі якщо процеси не завершилися
            p.kill()  # Примусове завершення
    except psutil.NoSuchProcess:
        pass

def restart_program(path):
    global process
    if process:
        print("Зупиняємо поточний процес та всі дочірні процеси")
        kill_process_and_children(process.pid)
        time.sleep(1)   # Невелика затримка перед перезапуском
    print("Перезапускаємо програму")
    start_program(path)

def wndproc(hwnd, msg, wparam, lparam):
    if msg == win32con.WM_POWERBROADCAST:
        if wparam == win32con.PBT_APMRESUMEAUTOMATIC or wparam == win32con.PBT_APMRESUMESUSPEND:
            print("Система вийшла з режиму сну")
            restart_program(program_path)
    return False

if __name__ == "__main__":
    # Завантажуємо шлях до програми з файлу settings.json
    program_path = load_settings()
    if not program_path:
        print("Помилка: шлях до програми не знайдено в settings.json")
        exit(1)

    print("*** Запуск моніторингу ***")
    hinst = win32api.GetModuleHandle(None)
    wndclass = win32gui.WNDCLASS()
    wndclass.hInstance = hinst
    wndclass.lpszClassName = "PowerMonitorWindowClass"
    CMPFUNC = CFUNCTYPE(c_bool, c_int, c_uint, c_uint, c_void_p)
    wndproc_pointer = CMPFUNC(wndproc)
    wndclass.lpfnWndProc = wndproc_pointer
    myWindowClass = win32gui.RegisterClass(wndclass)
    
    hwnd = win32gui.CreateWindowEx(
        win32con.WS_EX_LEFT,
        myWindowClass,
        "PowerMonitorWindow",
        0,
        0, 0, 0, 0,
        0, 0, hinst, None
    )
    
    if hwnd:
        # Реєстрація подій живлення
        result = windll.user32.RegisterPowerSettingNotification(HANDLE(hwnd), GUID_CONSOLE_DISPLAY_STATE, DWORD(0))
        print('Реєстрація події зміни живлення:', hex(result))
        print('Last Error:', win32api.GetLastError())
        
        # Запуск програми спочатку
        start_program(program_path)

        # Цикл для обробки повідомлень Windows
        print('\nВходимо в цикл повідомлень')
        while True:
            win32gui.PumpWaitingMessages()
            time.sleep(1)
    else:
        print("Не вдалося створити вікно.")
