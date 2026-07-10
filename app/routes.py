import io
from datetime import datetime, date, time
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from sqlalchemy import or_
from .extensions import db
from .models import (
    Client, Part, Status, Attribute, ClientAttribute, Car,
    Order, OrderStatus, Settings,
)
from .backup import export_csv, get_backup_dir

bp = Blueprint("main", __name__)


# ----------------------------------------------------------------------
# Главная — список клиентов
# ----------------------------------------------------------------------
@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    query = Client.query
    if q:
        query = (
            query.outerjoin(Client.orders)
            .outerjoin(Order.items)
            .filter(
                or_(
                    Client.name.ilike(f"%{q}%"),
                    Client.phone.ilike(f"%{q}%"),
                    OrderItem.part_name.ilike(f"%{q}%"),
                    OrderItem.article.ilike(f"%{q}%"),
                )
            )
            .distinct()
        )
    from .models import OrderItem
    clients = query.order_by(Client.created_at.desc()).all()
    return render_template("index.html", clients=clients, q=q)


# ----------------------------------------------------------------------
# Клиент — CRUD
# ----------------------------------------------------------------------
@bp.route("/client/add", methods=["GET", "POST"])
def client_add():
    if request.method == "POST":
        return _save_client()
    attributes = Attribute.query.all()
    statuses = Status.query.all()
    return render_template("client_form.html", client=None, attributes=attributes,
                           statuses=statuses, client_attrs={})


@bp.route("/client/<int:client_id>/edit", methods=["GET", "POST"])
def client_edit(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == "POST":
        return _save_client(client)
    attributes = Attribute.query.all()
    statuses = Status.query.all()
    client_attrs = {ca.attribute_id: ca.value for ca in client.attributes}
    return render_template("client_form.html", client=client, attributes=attributes,
                           statuses=statuses, client_attrs=client_attrs)


def _save_client(existing_client=None):
    from .models import OrderItem
    try:
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        status_id = int(request.form["status_id"])
        if not (name and phone):
            flash("ФИО и телефон обязательны", "warning")
            return redirect(request.referrer or url_for("main.index"))

        if existing_client:
            client = existing_client
        else:
            client = Client()
            db.session.add(client)

        client.name = name
        client.phone = phone
        client.status_id = status_id

        # Мессенджеры — сохраняем только если чекбокс активен
        client.telegram = request.form.get("telegram", "").strip() if request.form.get("tg_check") else None
        client.whatsapp = request.form.get("whatsapp", "").strip() if request.form.get("wa_check") else None
        client.max_account = request.form.get("max_account", "").strip() if request.form.get("max_check") else None

        db.session.flush()

        # Создание автомобиля (если заполнены поля)
        car_make = request.form.get("car_make", "").strip()
        car_model = request.form.get("car_model", "").strip()
        car_vin = request.form.get("car_vin", "").strip()
        car_year = request.form.get("car_year", "").strip()
        if car_make and car_vin:
            car = Car(
                client_id=client.id,
                make=car_make,
                model=car_model or "",
                vin=car_vin,
                year=int(car_year) if car_year else None,
            )
            db.session.add(car)

        for attr in Attribute.query.all():
            field_name = f"attr_{attr.id}"
            value = request.form.get(field_name, "").strip()
            ca = ClientAttribute.query.filter_by(client_id=client.id, attribute_id=attr.id).first()
            if value:
                if ca:
                    ca.value = value
                else:
                    db.session.add(ClientAttribute(client_id=client.id, attribute_id=attr.id, value=value))
            else:
                if ca:
                    db.session.delete(ca)

        db.session.commit()
        flash("Клиент успешно сохранён", "success")
        return redirect(url_for("main.index"))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Ошибка сохранения клиента")
        flash(f"Ошибка при сохранении клиента: {e}", "danger")
        return redirect(request.referrer or url_for("main.index"))


@bp.route("/client/<int:client_id>/delete", methods=["POST"])
def client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    try:
        db.session.delete(client)
        db.session.commit()
        flash("Клиент удалён", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при удалении клиента: {e}", "danger")
    return redirect(url_for("main.index"))


@bp.route("/client/<int:client_id>")
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)
    attributes = Attribute.query.all()
    client_attrs = {ca.attribute_id: ca.value for ca in client.attributes}
    return render_template("client_detail.html", client=client, attributes=attributes,
                           client_attrs=client_attrs)


# ----------------------------------------------------------------------
# Автомобили
# ----------------------------------------------------------------------
@bp.route("/client/<int:client_id>/car/add", methods=["GET", "POST"])
def car_add(client_id):
    if request.method == "POST":
        try:
            car = Car(
                client_id=client_id,
                make=request.form["make"].strip(),
                model=request.form["model"].strip(),
                vin=request.form["vin"].strip(),
                year=int(request.form.get("year")) if request.form.get("year") else None,
            )
            db.session.add(car)
            db.session.commit()
            flash("Автомобиль добавлен", "success")
            return redirect(url_for("main.client_detail", client_id=client_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при добавлении автомобиля: {e}", "danger")
    return render_template("car_form.html", car=None, client_id=client_id)


@bp.route("/car/<int:car_id>/edit", methods=["GET", "POST"])
def car_edit(car_id):
    car = Car.query.get_or_404(car_id)
    if request.method == "POST":
        try:
            car.make = request.form["make"].strip()
            car.model = request.form["model"].strip()
            car.vin = request.form["vin"].strip()
            year = request.form.get("year")
            car.year = int(year) if year else None
            db.session.commit()
            flash("Автомобиль обновлён", "success")
            return redirect(url_for("main.client_detail", client_id=car.client_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при обновлении автомобиля: {e}", "danger")
    return render_template("car_form.html", car=car, client_id=car.client_id)


@bp.route("/car/<int:car_id>/delete", methods=["POST"])
def car_delete(car_id):
    car = Car.query.get_or_404(car_id)
    client_id = car.client_id
    try:
        db.session.delete(car)
        db.session.commit()
        flash("Автомобиль удалён", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при удалении автомобиля: {e}", "danger")
    return redirect(url_for("main.client_detail", client_id=client_id))


# ----------------------------------------------------------------------
# Атрибуты клиента
# ----------------------------------------------------------------------
@bp.route("/client/<int:client_id>/attribute/<int:attr_id>/update", methods=["POST"])
def client_attribute_update(client_id, attr_id):
    client = Client.query.get_or_404(client_id)
    attribute = Attribute.query.get_or_404(attr_id)
    value = request.form.get("value", "").strip()
    try:
        ca = ClientAttribute.query.filter_by(client_id=client.id, attribute_id=attribute.id).first()
        if value:
            if ca:
                ca.value = value
            else:
                db.session.add(ClientAttribute(client_id=client.id, attribute_id=attribute.id, value=value))
        else:
            if ca:
                db.session.delete(ca)
        db.session.commit()
        flash("Атрибут обновлён", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при обновлении атрибута: {e}", "danger")
    return redirect(url_for("main.client_detail", client_id=client.id))


# ----------------------------------------------------------------------
# Статусы клиентов и заказов
# ----------------------------------------------------------------------
@bp.route("/statuses", methods=["GET", "POST"])
def status_list():
    if request.method == "POST":
        action = request.form.get("action")
        scope = request.form.get("scope", "client")
        try:
            if action == "add":
                name = request.form["name"].strip()
                if not name:
                    raise ValueError("Имя статуса обязательно")
                if scope == "order":
                    if OrderStatus.query.filter_by(name=name).first():
                        raise ValueError("Статус уже существует")
                    db.session.add(OrderStatus(name=name))
                else:
                    if Status.query.filter_by(name=name).first():
                        raise ValueError("Статус уже существует")
                    db.session.add(Status(name=name))
                db.session.commit()
                flash(f"Статус «{name}» добавлен", "success")
            elif action == "rename":
                status_id = int(request.form["status_id"])
                new_name = request.form["new_name"].strip()
                if not new_name:
                    raise ValueError("Новое имя пустое")
                if scope == "order":
                    status = OrderStatus.query.get_or_404(status_id)
                else:
                    status = Status.query.get_or_404(status_id)
                status.name = new_name
                db.session.commit()
                flash("Статус переименован", "success")
            elif action == "delete":
                status_id = int(request.form["status_id"])
                if scope == "order":
                    status = OrderStatus.query.get_or_404(status_id)
                    if Order.query.filter_by(status_id=status.id).first():
                        raise ValueError("Статус уже используется заказами")
                else:
                    status = Status.query.get_or_404(status_id)
                    if Client.query.filter_by(status_id=status.id).first():
                        raise ValueError("Статус уже используется клиентами")
                db.session.delete(status)
                db.session.commit()
                flash("Статус удалён", "info")
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка со статусом: {e}", "danger")
        return redirect(url_for("main.status_list"))
    statuses = Status.query.all()
    order_statuses = OrderStatus.query.all()
    return render_template("status_list.html", statuses=statuses, order_statuses=order_statuses)


@bp.route("/status/<int:status_id>/edit", methods=["GET", "POST"])
def status_edit(status_id):
    status = Status.query.get_or_404(status_id)
    if request.method == "POST":
        new_name = request.form["new_name"].strip()
        try:
            if not new_name:
                raise ValueError("Имя не может быть пустым")
            status.name = new_name
            db.session.commit()
            flash("Статус обновлён", "success")
            return redirect(url_for("main.status_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при обновлении статуса: {e}", "danger")
    return render_template("status_form.html", status=status)


# ----------------------------------------------------------------------
# Атрибуты (справочник)
# ----------------------------------------------------------------------
@bp.route("/attributes", methods=["GET", "POST"])
def attribute_list():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "add":
                name = request.form["name"].strip()
                if not name:
                    raise ValueError("Имя атрибута обязательно")
                if Attribute.query.filter_by(name=name).first():
                    raise ValueError("Атрибут уже существует")
                db.session.add(Attribute(name=name))
                db.session.commit()
                flash(f"Атрибут «{name}» добавлен", "success")
            elif action == "rename":
                attr_id = int(request.form["attr_id"])
                new_name = request.form["new_name"].strip()
                attr = Attribute.query.get_or_404(attr_id)
                if not new_name:
                    raise ValueError("Новое имя пустое")
                attr.name = new_name
                db.session.commit()
                flash("Атрибут переименован", "success")
            elif action == "delete":
                attr_id = int(request.form["attr_id"])
                attr = Attribute.query.get_or_404(attr_id)
                ClientAttribute.query.filter_by(attribute_id=attr.id).delete()
                db.session.delete(attr)
                db.session.commit()
                flash("Атрибут удалён", "info")
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка с атрибутом: {e}", "danger")
        return redirect(url_for("main.attribute_list"))
    attributes = Attribute.query.all()
    return render_template("attribute_list.html", attributes=attributes)


@bp.route("/attribute/<int:attr_id>/edit", methods=["GET", "POST"])
def attribute_edit(attr_id):
    attr = Attribute.query.get_or_404(attr_id)
    if request.method == "POST":
        new_name = request.form["new_name"].strip()
        try:
            if not new_name:
                raise ValueError("Имя не может быть пустым")
            attr.name = new_name
            db.session.commit()
            flash("Атрибут обновлён", "success")
            return redirect(url_for("main.attribute_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при обновлении атрибута: {e}", "danger")
    return render_template("attribute_form.html", attribute=attr)


# ----------------------------------------------------------------------
# Статистика за сегодня
# ----------------------------------------------------------------------
@bp.route("/stats")
def stats():
    today = date.today()
    start_dt = datetime.combine(today, time.min)
    end_dt = datetime.combine(today, time.max)

    from .models import Order, OrderStatus
    todays_orders = Order.query.filter(Order.created_at.between(start_dt, end_dt)).all()
    active_today = sum(1 for o in todays_orders if o.status and o.status.name == "В работе")
    done_today = sum(1 for o in todays_orders if o.status and o.status.name == "Выдан")
    cancelled_today = sum(1 for o in todays_orders if o.status and o.status.name == "Отменён")

    todays_clients = Client.query.filter(Client.created_at.between(start_dt, end_dt)).all()
    count = len(todays_clients)
    total = sum(c.total_price for c in todays_clients)

    return render_template(
        "stats.html",
        count=count, total=total,
        today_str=today.strftime("%d.%m.%Y"),
        clients=todays_clients,
        active_today=active_today, done_today=done_today, cancelled_today=cancelled_today,
    )


# ----------------------------------------------------------------------
# Настройки + экспорт CSV
# ----------------------------------------------------------------------
@bp.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        backup_dir = request.form.get("backup_dir", "").strip()
        employee = request.form.get("employee", "").strip()
        shop_address = request.form.get("shop_address", "").strip()
        backup_retention_days = request.form.get("backup_retention_days", "90").strip()
        ui_scale = request.form.get("ui_scale", "100").strip()
        try:
            if backup_dir and not __import__("os").path.isdir(backup_dir):
                flash("Папка бэкапов не найдена — поле не сохранено. Укажите существующую папку.", "warning")
            else:
                Settings.set("backup_dir", backup_dir)
            Settings.set("employee", employee)
            Settings.set("shop_address", shop_address)
            Settings.set("backup_retention_days", backup_retention_days)
            Settings.set("ui_scale", ui_scale)
            db.session.commit()
            flash("Настройки сохранены", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка сохранения настроек: {e}", "danger")
        return redirect(url_for("main.settings_page"))
    return render_template(
        "settings.html",
        backup_dir=Settings.get("backup_dir"),
        employee=Settings.get("employee"),
        shop_address=Settings.get("shop_address"),
        backup_retention_days=Settings.get("backup_retention_days", "90"),
        ui_scale=Settings.get("ui_scale", "100"),
    )


@bp.route("/export/csv", methods=["POST"])
def export_csv_manual():
    filepath = export_csv()
    if filepath:
        flash(f"CSV экспортирован: {filepath}", "success")
    else:
        flash("Не удалось экспортировать CSV. Проверьте папку бэкапов в настройках.", "danger")
    return redirect(request.referrer or url_for("main.index"))


@bp.route("/invoice/select", methods=["GET", "POST"])
def invoice_select():
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        order_id = request.form.get("order_id", type=int)
        if client_id:
            url = url_for("main.client_invoice_pdf", client_id=client_id)
            if order_id:
                url += f"?order_id={order_id}"
            return redirect(url)
        flash("Выберите клиента", "warning")
        return redirect(url_for("main.invoice_select"))

    clients = Client.query.order_by(Client.name).all()
    return render_template("invoice_select.html", clients=clients)


@bp.route("/api/client/<int:client_id>/orders")
def api_client_orders(client_id):
    orders = Order.query.filter_by(client_id=client_id).order_by(Order.created_at.desc()).all()
    return jsonify([{
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status.name if o.status else "",
    } for o in orders])


@bp.route("/client/<int:client_id>/invoice/pdf")
def client_invoice_pdf(client_id):
    from flask import send_file
    from .pdf_invoice import generate_invoice_pdf

    client = Client.query.get_or_404(client_id)
    order_id = request.args.get("order_id", type=int)
    order = Order.query.get(order_id) if order_id else None

    employee = Settings.get("employee")
    shop_address = Settings.get("shop_address")
    pdf_bytes = generate_invoice_pdf(client, order=order, employee=employee, shop_address=shop_address)

    filename = f"invoice_{client.name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@bp.route("/activate", methods=["GET", "POST"])
def activate():
    from .models import Settings
    s = Settings.query.filter_by(key="licensed").first()
    if s and s.value == "1":
        flash("Программа уже лицензирована", "info")
        return redirect(url_for("main.index"))
    if request.method == "POST":
        from .license import activate_key
        key = request.form.get("key", "").strip()
        if key:
            ok, msg = activate_key(key)
            if ok:
                flash(msg, "success")
                return redirect(url_for("main.index"))
            else:
                flash(msg, "danger")
        else:
            flash("Введите ключ", "warning")
    return render_template("activate.html")
