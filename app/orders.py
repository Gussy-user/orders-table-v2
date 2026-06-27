from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .extensions import db
from .models import Order, OrderItem, OrderStatus, Client, Part
from .backup import export_csv

bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.route("/")
def orders_active():
    orders = Order.query.filter_by(archived=False).order_by(Order.created_at.desc()).all()
    statuses = OrderStatus.query.all()
    return render_template("order_list.html", orders=orders, archived=False, statuses=statuses)


@bp.route("/archive")
def orders_archive():
    orders = Order.query.filter_by(archived=True).order_by(Order.created_at.desc()).all()
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

            now = datetime.now()
            base = now.strftime("ORD-%Y%m%d")
            similar = Order.query.filter(Order.order_number.like(f"{base}%")).count()
            order_number = f"{base}-{similar + 1:04d}"

            order = Order(
                client_id=client_id,
                status_id=status_id,
                order_number=order_number,
            )
            db.session.add(order)
            db.session.flush()

            part_names = request.form.getlist("part_name")
            articles = request.form.getlist("article")
            quantities = request.form.getlist("quantity")
            prices = request.form.getlist("price")

            for name, art, qty, price in zip(part_names, articles, quantities, prices):
                if not name.strip():
                    continue
                item = OrderItem(
                    order_id=order.id,
                    part_name=name.strip(),
                    article=art.strip() if art else "",
                    quantity=int(qty) if qty else 1,
                    price=float(price) if price else 0,
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
    client_id = request.args.get("client_id", type=int)
    return render_template(
        "order_form.html",
        clients=clients, statuses=statuses,
        preselected_client_id=client_id, order=None,
    )


@bp.route("/<int:order_id>/edit", methods=["GET", "POST"])
def order_edit(order_id):
    order = Order.query.get_or_404(order_id)

    if request.method == "POST":
        try:
            order.client_id = int(request.form["client_id"])
            order.status_id = int(request.form["status_id"])

            OrderItem.query.filter_by(order_id=order.id).delete()

            part_names = request.form.getlist("part_name")
            articles = request.form.getlist("article")
            quantities = request.form.getlist("quantity")
            prices = request.form.getlist("price")

            for name, art, qty, price in zip(part_names, articles, quantities, prices):
                if not name.strip():
                    continue
                item = OrderItem(
                    order_id=order.id,
                    part_name=name.strip(),
                    article=art.strip() if art else "",
                    quantity=int(qty) if qty else 1,
                    price=float(price) if price else 0,
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
    return render_template(
        "order_form.html",
        clients=clients, statuses=statuses,
        order=order, preselected_client_id=order.client_id,
    )


@bp.route("/<int:order_id>/status", methods=["POST"])
def order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status_id = int(request.form.get("status_id", 0))
    status = OrderStatus.query.get(status_id)
    if status:
        order.status_id = status_id
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
