@echo off
echo === Orders Table - Windows ===
echo.

REM Проверяем Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден. Установите Python 3.10+ с python.org
    pause
    exit /b 1
)

REM Устанавливаем зависимости
echo Установка зависимостей...
pip install -r requirements.txt
echo.

REM Запускаем
echo Запуск приложения...
python run.py
