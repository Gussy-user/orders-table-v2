# Калькулятор стоимости заказа для типографии с PDF-сметой

## Стек технологий
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: Jinja2 + Bootstrap 5 (CDN) + vanilla JS
- **PDF**: ReportLab
- **Язык интерфейса**: Русский

## Расположение
Папка `/Users/bogdanparilov/printshop-calculator` (на уровне с `orders-table-v2`)

---

## Структура файлов

```
printshop-calculator/
├── run.py                         # Точка входа
├── requirements.txt               # Зависимости
├── printshop/
│   ├── __init__.py                # Создание FastAPI app
│   ├── config.py                  # Настройки (секретный ключ, путь к БД)
│   ├── database.py                # SQLAlchemy engine + session
│   ├── models.py                  # Все модели БД
│   ├── auth.py                    # Логика авторизации (session-based)
│   ├── pricing.py                 # Движок расчёта цен
│   ├── pdf_generator.py           # Генерация PDF-сметы
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth_routes.py         # /login, /logout
│   │   ├── calculator.py          # /calculator — главная страница
│   │   ├── estimates.py           # /estimates — CRUD смет
│   │   ├── admin.py               # /admin — настройки цен, типов продукции
│   │   └── settings.py            # /settings — данные типографии
│   └── templates/
│       ├── base.html              # Layout с навбаром
│       ├── login.html             # Страница входа
│       ├── calculator.html        # Калькулятор (главная)
│       ├── estimate_detail.html   # Просмотр сметы
│       ├── estimates_list.html    # История смет
│       ├── admin/
│       │   ├── dashboard.html     # Админ-панель
│       │   ├── product_types.html # Управление типами продукции
│       │   ├── product_form.html  # Форма типа продукции
│       │   ├── paper_types.html   # Управление типами бумаги
│       │   ├── formats.html       # Управление форматами
│       │   ├── color_modes.html   # Управление цветностями
│       │   ├── finishing.html     # Управление послепечатной обработкой
│       │   ├── discounts.html     # Управление скидками за тираж
│       │   └── base_prices.html   # Управление базовыми ценами
│       └── settings/
│           └── company.html       # Настройки типографии
├── static/
│   ├── css/style.css
│   └── js/
│       ├── calculator.js          # Логика калькулятора (AJAX расчёт)
│       └── admin.js
├── uploads/                       # Логотипы и прочие файлы
└── instance/
    └── printshop.db               # SQLite база
```

---

## Модели базы данных

### User
```python
id, username, password_hash, is_admin, created_at
```

### ProductType
```python
id, name, slug, description, is_active, sort_order
# slug: "vizitki", "listovki", "broshury", "bannery", "naklejki", "papki", "kalendari", "bloknoty"
```

### PaperType
```python
id, name, price_per_sheet, is_active, sort_order
# "Мелованная 115г", "Мелованная 150г", "Мелованная 300г", "Офсетная", "Дизайнерская"
```

### PrintFormat
```python
id, name, width_mm, height_mm, is_custom, base_price_multiplier, is_active
# А6(105×148), А5(148×210), А4(210×297), А3(297×420), Нестандарт(ввод мм)
```

### ColorMode
```python
id, name, price_multiplier, is_active
# "4+0 (односторонняя)", "4+4 (двусторонняя)", "1+0 (ч/б)", "1+1 (ч/б двусторонняя)"
```

### FinishingType
```python
id, name, price, is_active
# "Ламинация матовая", "Ламинация глянцевая", "Ламинация soft-touch",
# "Биговка", "Перфорация", "Скругление углов"
```

### DesignOption
```python
id, name, price, is_active
# "Макет есть у клиента (0₽)", "Разработка макета (1500₽)"
```

### DiscountTier
```python
id, min_quantity, max_quantity, discount_percent
# 0-99: 0%, 100-499: 5%, 500-999: 10%, 1000+: 15%
```

### Estimate (смета)
```python
id, estimate_number (авто: "2024-047"), client_name, client_phone, client_email,
manager_name, urgency ("standard"/"urgent"), total_price, discount_amount,
status ("draft"/"confirmed"/"in_progress"/"ready"), created_at, updated_at, notes
```

### EstimateItem (позиция в смете — мультизаказ)
```python
id, estimate_id (FK), product_type_id (FK), paper_type_id (FK),
format_id (FK), custom_width_mm, custom_height_mm, color_mode_id (FK),
quantity, design_option_id (FK),
finishing_ids (JSON — список ID выбранной обработки),
calculated_price, breakdown_json (JSON — детализация: печать=X, ламинация=Y, ...)
```

### CompanySettings
```python
id, key, value
# company_name, company_address, company_phone, company_email,
# logo_path, advance_payment_percent (50), estimate_validity_days (7),
# standard_deadline, urgent_deadline
```

---

## Логика расчёта цен (pricing.py)

```
calculate_price(product_type, paper, format, color_mode, finishing_list, design_option, quantity, urgency):

  base_price = product_type.base_price  # из ProductType или связанной таблицы цен
  paper_cost = paper.price_per_sheet * quantity
  format_mult = format.base_price_multiplier  # А3 = x2, А4 = x1, А5 = x0.6, А6 = x0.35
  color_mult = color_mode.price_multiplier   # 4+4 = x1, 4+0 = x0.65, 1+0 = x0.35, 1+1 = x0.5

  printing_cost = base_price * quantity * format_mult * color_mult
  finishing_cost = sum(f.price for f in finishing_list) * quantity
  design_cost = design_option.price
  subtotal = printing_cost + finishing_cost + design_cost

  # Скидка за тираж
  discount = get_discount(subtotal, quantity)  # из DiscountTier

  # Коэффициент срочности
  urgency_mult = 1.3 if urgency == "urgent" else 1.0

  total = (subtotal - discount) * urgency_mult

  return { total, breakdown: { printing, finishing, design, discount, urgency_mult } }
```

---

## PDF-смета (pdf_generator.py)

Используем ReportLab. Структура:
1. **Шапка**: логотип (слева) + номер сметы и дата (справа)
2. **Данные типографии**: название, адрес, телефон
3. **Данные клиента**: имя, телефон, email
4. **Таблица позиций**: для каждой позиции — описание (тип, формат, бумага, цветность, ламинация, обработка), тираж, сумма
5. **Итого строка**: общая сумма + скидка + доплата за срочность
6. **Подвал**: срок действия, условия предоплаты

---

## Роуты

| Метод | Путь | Описание |
|-------|------|----------|
| GET/POST | `/login` | Авторизация |
| GET | `/logout` | Выход |
| GET | `/` | Калькулятор (главная) |
| POST | `/api/calculate` | AJAX расчёт стоимости (JSON) |
| POST | `/estimates/create` | Создать смету |
| GET | `/estimates/` | История смет |
| GET | `/estimates/{id}` | Просмотр сметы |
| POST | `/estimates/{id}/duplicate` | Дублировать смету |
| POST | `/estimates/{id}/status` | Изменить статус |
| GET | `/estimates/{id}/pdf` | Скачать PDF |
| GET | `/admin/` | Админ-панель |
| CRUD | `/admin/product-types/` | Типы продукции |
| CRUD | `/admin/paper-types/` | Типы бумаги |
| CRUD | `/admin/formats/` | Форматы |
| CRUD | `/admin/color-modes/` | Цветности |
| CRUD | `/admin/finishing/` | Послепечатная обработка |
| CRUD | `/admin/discounts/` | Скидки за тираж |
| CRUD | `/admin/base-prices/` | Базовые цены |
| GET/POST | `/settings/company` | Настройки типографии |

---

## Порядок реализации

### Этап 1: Каркас приложения
1. Создать структуру папок и файлов
2. `config.py`, `database.py`, `models.py` — все модели
3. `auth.py` — авторизация (passlib + bcrypt)
4. `base.html` — layout с навбаром
5. `login.html` + роуты авторизации
6. Seed-данные: admin пользователь + начальные типы продукции/бумаги/форматов

### Этап 2: Калькулятор
7. `calculator.html` — форма с динамическими параметрами (AJAX)
8. `pricing.py` — движок расчёта цен
9. `POST /api/calculate` — endpoint расчёта
10. `calculator.js` — клиентская логика (выбор типа → показ параметров → запрос расчёта → отображение цены)

### Этап 3: Сметы
11. `estimates.py` — CRUD смет (создание, просмотр, список)
12. `estimate_detail.html` — просмотр сметы с детализацией
13. `estimates_list.html` — история с фильтрами
14. Дублирование и смена статуса

### Этап 4: PDF
15. `pdf_generator.py` — генерация PDF с логотипом
16. Экспорт PDF по кнопке

### Этап 5: Админ-панель
17. CRUD для всех справочников (типы продукции, бумага, форматы, цветность, обработка)
18. Управление скидками за тираж
19. Управление базовыми ценами
20. Настройки типографии (данные + логотип)

---

## Верификация
1. `pip install -r requirements.txt` — зависимости ставятся
2. `python run.py` — приложение запускается на http://localhost:8000
3. Вход под admin/admin → видим калькулятор
4. Выбираем "Листовки" → заполняем параметры → видим цену (AJAX)
5. Создаём смету → она появляется в списке
6. Скачиваем PDF → открывается красивая смета с логотипом
7. В админке меняем цену бумаги → пересчитываем → цена изменилась
8. Тестируем срочность (+30%) и скидки за тираж
