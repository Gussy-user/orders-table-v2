from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .extensions import db
from .models import Order, OrderItem, OrderStatus, Client, Part
from .backup import export_csv

bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.route("/")
def orders_active():
    orders = Order.query.filter(
        Order.archived == False,
        Order.is_archived_manually == False,
    ).order_by(Order.created_at.desc()).all()
    statuses = OrderStatus.query.all()
    return render_template("order_list.html", orders=orders, archived=False, statuses=statuses)


@bp.route("/archive")
def orders_archive():
    orders = Order.query.filter(
        (Order.archived == True) | (Order.is_archived_manually == True)
    ).order_by(Order.created_at.desc()).all()
    statuses = OrderStatus.query.all()
    return render_template("order_list.html", orders=orders, archived=True, statuses=statuses)


@bp.route("/<int:order_id>")
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("order_detail.html", order=order)


@bp.route("/add", methods=["GET", "POST"])
def order_add():
    if request.method == "POST":
        try:
            client_id = int(request.form["client_id"])
            status_id = int(request.form["status_id"])
            payment_status = request.form.get("payment_status", "Не оплачен")

            now = datetime.now()
            base = now.strftime("ORD-%Y%m%d")
            similar = Order.query.filter(Order.order_number.like(f"{base}%")).count()
            order_number = f"{base}-{similar + 1:04d}"

            prepayment = float(request.form.get("prepayment", 0) or 0)

            order = Order(
                client_id=client_id,
                status_id=status_id,
                order_number=order_number,
                payment_status=payment_status,
                prepayment=prepayment,
            )
            db.session.add(order)
            db.session.flush()

            part_ids = request.form.getlist("part_id")
            part_names = request.form.getlist("part_name")
            articles = request.form.getlist("article")
            quantities = request.form.getlist("quantity")
            prices = request.form.getlist("price")
            item_statuses = request.form.getlist("item_status")

            for i, name in enumerate(part_names):
                if not name.strip():
                    continue
                part_id = int(part_ids[i]) if part_ids[i] else None
                item = OrderItem(
                    order_id=order.id,
                    part_id=part_id,
                    part_name=name.strip(),
                    article=articles[i].strip() if articles[i] else "",
                    quantity=int(quantities[i]) if quantities[i] else 1,
                    price=float(prices[i]) if prices[i] else 0,
                    item_status=item_statuses[i] if i < len(item_statuses) else "Ожидается",
                )
                db.session.add(item)

            db.session.commit()
            export_csv()
            flash(f"Заказ №{order_number} создан", "success")
            return redirect(url_for("orders.order_detail", order_id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при создании заказа: {e}", "danger")
            return redirect(url_for("orders.order_add"))

    clients = Client.query.all()
    statuses = OrderStatus.query.all()
    parts = Part.query.order_by(Part.name).all()
    client_id = request.args.get("client_id", type=int)
    return render_template(
        "order_form.html",
        clients=clients, statuses=statuses, parts=parts,
        preselected_client_id=client_id, order=None,
    )


@bp.route("/<int:order_id>/edit", methods=["GET", "POST"])
def order_edit(order_id):
    order = Order.query.get_or_404(order_id)

    if request.method == "POST":
        try:
            order.client_id = int(request.form["client_id"])
            order.status_id = int(request.form["status_id"])
            order.payment_status = request.form.get("payment_status", order.payment_status)
            order.prepayment = float(request.form.get("prepayment", 0) or 0)

            OrderItem.query.filter_by(order_id=order.id).delete()

            part_ids = request.form.getlist("part_id")
            part_names = request.form.getlist("part_name")
            articles = request.form.getlist("article")
            quantities = request.form.getlist("quantity")
            prices = request.form.getlist("price")
            item_statuses = request.form.getlist("item_status")

            for i, name in enumerate(part_names):
                if not name.strip():
                    continue
                part_id = int(part_ids[i]) if part_ids[i] else None
                item = OrderItem(
                    order_id=order.id,
                    part_id=part_id,
                    part_name=name.strip(),
                    article=articles[i].strip() if articles[i] else "",
                    quantity=int(quantities[i]) if quantities[i] else 1,
                    price=float(prices[i]) if prices[i] else 0,
                    item_status=item_statuses[i] if i < len(item_statuses) else "Ожидается",
                )
                db.session.add(item)

            db.session.commit()
            export_csv()
            flash(f"Заказ №{order.order_number} обновлён", "success")
            return redirect(url_for("orders.order_detail", order_id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при обновлении заказа: {e}", "danger")

    clients = Client.query.all()
    statuses = OrderStatus.query.all()
    parts = Part.query.order_by(Part.name).all()
    return render_template(
        "order_form.html",
        clients=clients, statuses=statuses, parts=parts,
        order=order, preselected_client_id=order.client_id,
    )


@bp.route("/<int:order_id>/status", methods=["POST"])
def order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status_id = int(request.form.get("status_id", 0))
    status = OrderStatus.query.get(status_id)
    if status:
        old_status = order.status.name if order.status else ""
        order.status_id = status_id
        db.session.flush()

        # Автосписание товара со склада при выдаче
        from .models import Settings, Part
        auto_deduct = Settings.get("auto_deduct", "1") == "1"
        if auto_deduct and status.name == "Выдан" and old_status != "Выдан":
            warnings = []
            for item in order.items:
                if item.part_id:
                    part = Part.query.get(item.part_id)
                    if part:
                        if part.quantity >= item.quantity:
                            part.quantity -= item.quantity
                        else:
                            warnings.append(f"{part.name}: нужно {item.quantity}, есть {part.quantity}")
                            part.quantity = 0
            if warnings:
                flash("Внимание: " + "; ".join(warnings), "warning")

        db.session.commit()
        export_csv()
        flash(f"Статус заказа №{order.order_number} изменён", "success")
    return redirect(request.referrer or url_for("orders.orders_active"))


@bp.route("/<int:order_id>/toggle_archive", methods=["POST"])
def toggle_archive(order_id):
    order = Order.query.get_or_404(order_id)
    order.archived = not order.archived
    try:
        db.session.commit()
        export_csv()
        flash("Заказ отправлен в архив" if order.archived else "Заказ восстановлен", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {e}", "danger")
    return redirect(request.referrer or url_for("orders.orders_active"))


@bp.route("/<int:order_id>/manual_archive", methods=["POST"])
def manual_archive(order_id):
    order = Order.query.get_or_404(order_id)
    order.is_archived_manually = True
    try:
        db.session.commit()
        export_csv()
        flash(f"Заказ №{order.order_number} отправлен в архив", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {e}", "danger")
    return redirect(request.referrer or url_for("orders.orders_active"))


@bp.route("/<int:order_id>/manual_unarchive", methods=["POST"])
def manual_unarchive(order_id):
    order = Order.query.get_or_404(order_id)
    order.is_archived_manually = False
    try:
        db.session.commit()
        export_csv()
        flash(f"Заказ №{order.order_number} восстановлен из архива", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка: {e}", "danger")
    return redirect(request.referrer or url_for("orders.orders_archive"))


@bp.route("/<int:order_id>/delete", methods=["POST"])
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    try:
        db.session.delete(order)
        db.session.commit()
        export_csv()
        flash(f"Заказ №{order.order_number} удалён", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при удалении: {e}", "danger")
    return redirect(url_for("orders.orders_active"))


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    orders = []
    if q:
        orders = (
            Order.query.join(Client)
            .filter(
                (Order.order_number.ilike(f"%{q}%"))
                | (Client.name.ilike(f"%{q}%"))
                | (Client.phone.ilike(f"%{q}%"))
                | (Client.id == q)
                | (Order.id == q)
            )
            .order_by(Order.created_at.desc())
            .all()
        )
    return render_template("order_search.html", orders=orders, q=q)
