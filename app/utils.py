import os
import sys


def resource_path(relative_path: str) -> str:
    """Возвращает абсолютный путь. Работает и в обычном запуске, и в PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


def data_path(relative_path: str) -> str:
    """Путь к данным рядом с exe (не внутри _MEIPASS)."""
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)
