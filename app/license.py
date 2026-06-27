import hashlib
import secrets
from datetime import datetime
from .extensions import db
from .models import License, Settings


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_onepass_keys(count: int = 10) -> list[str]:
    keys = []
    for _ in range(count):
        raw = secrets.token_hex(8).upper()
        raw_fmt = f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"
        h = _hash_key(raw_fmt)
        if not License.query.filter_by(key=h).first():
            db.session.add(License(key=h, key_type="onepass"))
            keys.append(raw_fmt)
    db.session.commit()
    return keys


def generate_master_key() -> str:
    raw = f"MASTER-{secrets.token_hex(12).upper()}"
    raw_fmt = f"{raw[:11]}-{raw[11:15]}-{raw[15:19]}-{raw[19:23]}"
    h = _hash_key(raw_fmt)
    if not License.query.filter_by(key=h).first():
        db.session.add(License(key=h, key_type="master"))
        db.session.commit()
    return raw_fmt


def activate_key(raw_key: str) -> tuple[bool, str]:
    h = _hash_key(raw_key.strip().upper())
    lic = License.query.filter_by(key=h).first()
    if not lic:
        return False, "Неверный ключ"
    if lic.key_type == "onepass":
        if lic.used:
            return False, "Ключ уже использован"
        lic.used = True
        lic.activated_at = datetime.utcnow()
        db.session.commit()
        Settings.set("licensed", "1")
        return True, "Лицензия активирована"
    elif lic.key_type == "master":
        lic.activated_at = datetime.utcnow()
        db.session.commit()
        Settings.set("licensed", "1")
        return True, "Лицензия активирована (master)"
    return False, "Неизвестный тип ключа"


def is_licensed() -> bool:
    return Settings.get("licensed") == "1"
