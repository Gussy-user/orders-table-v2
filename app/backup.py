import os
import sys
import datetime
from .extensions import db
from .models import Order, OrderItem, Settings


def _program_dir() -> str:
    """Путь к каталогу, где лежит run.py (или .exe)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_backup_dir() -> str:
    d = Settings.get("backup_dir", "")
    if d and os.path.isdir(d):
        return d
    return _program_dir()


def export_csv():
    backup_dir = get_backup_dir()
    if not os.path.isdir(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(backup_dir, f"orders_{timestamp}.csv")

    orders = Order.query.order_by(Order.created_at.desc()).all()

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = __import__("csv").writer(f, delimiter=";")
        writer.writerow([
            "Номер заказа", "Клиент", "Телефон", "Деталь", "Артикул",
            "Кол-во", "Цена за шт.", "Сумма", "Статус", "Дата",
        ])
        for o in orders:
            for item in o.items:
                writer.writerow([
                    o.order_number,
                    o.client.name if o.client else "",
                    o.client.phone if o.client else "",
                    item.part_name,
                    item.article or "",
                    item.quantity,
                    f"{item.price:.2f}",
                    f"{item.total:.2f}",
                    o.status.name if o.status else "",
                    o.created_at.strftime("%d.%m.%y %H:%M") if o.created_at else "",
                ])

    return filepath


def cleanup_old_backups():
    backup_dir = get_backup_dir()
    if not os.path.isdir(backup_dir):
        return

    try:
        retention_days = int(Settings.get("backup_retention_days", "90"))
    except (ValueError, TypeError):
        retention_days = 90

    cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    deleted = 0

    for filename in os.listdir(backup_dir):
        if not filename.startswith("orders_"):
            continue
        if not (filename.endswith(".csv") or filename.endswith(".xlsx")):
            continue
        filepath = os.path.join(backup_dir, filename)
        if not os.path.isfile(filepath):
            continue
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
        if mtime < cutoff:
            try:
                os.remove(filepath)
                deleted += 1
            except OSError:
                pass

    return deleted
