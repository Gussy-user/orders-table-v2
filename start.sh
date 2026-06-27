#!/bin/bash
echo "=== Orders Table ==="
echo

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "ОШИБКА: Python3 не найден"
    exit 1
fi

# Устанавливаем зависимости
echo "Установка зависимостей..."
pip3 install -r requirements.txt
echo

# Запускаем
echo "Запуск приложения..."
python3 run.py
