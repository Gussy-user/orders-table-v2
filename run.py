import sys
import os
import time
import platform
import subprocess
import webbrowser
import threading

from app import create_app
from app.utils import data_path

app = create_app()

HOST = "127.0.0.1"
PORT = 5001
URL = f"http://{HOST}:{PORT}"

# Стандартные пути к Chrome
CHROME_PATHS_WINDOWS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
]


def find_chrome() -> str | None:
    """Ищет исполняемый файл Google Chrome. Возвращает путь или None."""
    system = platform.system()

    if system == "Windows":
        # 1. Проверяем стандартные пути
        for path in CHROME_PATHS_WINDOWS:
            if os.path.isfile(path):
                return path

        # 2. Пробуем через where
        try:
            result = subprocess.run(
                ["where", "chrome"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().splitlines()[0]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    elif system == "Darwin":
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(mac_path):
            return mac_path

    elif system == "Linux":
        for cmd in ["google-chrome", "google-chrome-stable", "chromium-browser"]:
            try:
                result = subprocess.run(
                    ["which", cmd], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    return None


def open_browser(url: str):
    """Открывает URL в Chrome или в браузере по умолчанию."""
    chrome_path = find_chrome()
    if chrome_path:
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.Popen([chrome_path, url])
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", chrome_path, url])
            else:
                subprocess.Popen([chrome_path, url])
            return
        except (OSError, FileNotFoundError):
            pass

    # Fallback — браузер по умолчанию
    webbrowser.open_new(url)


def start_server():
    """Запускает Flask-сервер."""
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    # Запускаем сервер в фоновом потоке
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Ждём пока сервер поднимется
    time.sleep(1.5)

    # Открываем браузер
    open_browser(URL)

    # Блокируем основной поток (сервер работает)
    server_thread.join()
