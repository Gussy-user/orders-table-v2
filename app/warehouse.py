from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import or_
from .extensions import db
from .models import Part, Attribute, PartAttribute, StockHistory

bp = Blueprint("warehouse", __name__, url_prefix="/warehouse")


@bp.route("/")
def parts_list():
    q = request.args.get("q", "").strip()
    query = Part.query
    if q:
        query = query.filter(
            or_(
                Part.name.ilike(f"%{q}%"),
                Part.article.ilike(f"%{q}%"),
                Part.location.ilike(f"%{q}%"),
            )
        )
    parts = query.order_by(Part.name).all()
    return render_template("warehouse_list.html", parts=parts, q=q)


@bp.route("/add", methods=["GET", "POST"])
def part_add():
    if request.method == "POST":
        try:
            part = Part(
                name=request.form["name"].strip(),
                article=request.form.get("article", "").strip() or None,
                quantity=int(request.form.get("quantity", 0) or 0),
                price=float(request.form["price"]),
                purchase_price=float(request.form.get("purchase_price", 0) or 0),
                location=request.form.get("location", "На складе").strip(),
            )
            db.session.add(part)
            db.session.flush()

            from .models import log_stock_operation
            if part.quantity > 0:
                log_stock_operation(part.id, part.name, "ADD", part.quantity)

            # Сохранение атрибутов склада
            for attr in Attribute.query.filter_by(entity_type="stock").all():
                value = request.form.get(f"sattr_{attr.id}", "").strip()
                if value:
                    db.session.add(PartAttribute(part_id=part.id, attribute_id=attr.id, value=value))

            db.session.commit()
            flash(f"Деталь «{part.name}» добавлена", "success")
            return redirect(url_for("warehouse.parts_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при добавлении детали: {e}", "danger")

    stock_attributes = Attribute.query.filter_by(entity_type="stock").all()
    return render_template("warehouse_form.html", part=None, stock_attributes=stock_attributes, stock_attrs={})


@bp.route("/<int:part_id>/edit", methods=["GET", "POST"])
def part_edit(part_id):
    part = Part.query.get_or_404(part_id)
    if request.method == "POST":
        try:
            old_quantity = part.quantity
            old_name = part.name
            old_article = part.article or ""
            old_price = part.price
            old_purchase_price = part.purchase_price or 0
            old_location = part.location or ""

            part.name = request.form["name"].strip()
            part.article = request.form.get("article", "").strip() or None
            part.quantity = int(request.form.get("quantity", 0) or 0)
            part.price = float(request.form["price"])
            part.purchase_price = float(request.form.get("purchase_price", 0) or 0)
            part.location = request.form.get("location", "На складе").strip()

            from .models import log_stock_operation
            qty_diff = part.quantity - old_quantity
            if qty_diff != 0:
                log_stock_operation(part.id, part.name, "ADD" if qty_diff > 0 else "WRITE_OFF", qty_diff)

            # Логирование изменений полей
            changes = []
            if old_name != part.name:
                changes.append(f"Название: {old_name} → {part.name}")
            if old_article != (part.article or ""):
                changes.append(f"Артикул: {old_article or '—'} → {part.article or '—'}")
            if old_price != part.price:
                changes.append(f"Цена: {old_price} → {part.price}")
            if old_purchase_price != (part.purchase_price or 0):
                changes.append(f"Закупка: {old_purchase_price} → {part.purchase_price or 0}")
            if old_location != (part.location or ""):
                changes.append(f"Место: {old_location or '—'} → {part.location or '—'}")
            if changes:
                log_stock_operation(part.id, part.name, "EDIT", 0, details="; ".join(changes))

            # Сохранение атрибутов склада
            PartAttribute.query.filter_by(part_id=part.id).delete()
            for attr in Attribute.query.filter_by(entity_type="stock").all():
                value = request.form.get(f"sattr_{attr.id}", "").strip()
                if value:
                    db.session.add(PartAttribute(part_id=part.id, attribute_id=attr.id, value=value))

            db.session.commit()
            flash("Деталь обновлена", "success")
            return redirect(url_for("warehouse.parts_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при обновлении детали: {e}", "danger")

    stock_attributes = Attribute.query.filter_by(entity_type="stock").all()
    stock_attrs = {pa.attribute_id: pa.value for pa in part.attributes}
    return render_template("warehouse_form.html", part=part, stock_attributes=stock_attributes, stock_attrs=stock_attrs)


@bp.route("/history/")
def stock_history():
    q = request.args.get("q", "").strip()
    op_type = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = StockHistory.query

    if q:
        query = query.filter(StockHistory.product_name.ilike(f"%{q}%"))
    if op_type:
        query = query.filter(StockHistory.operation_type == op_type)
    if date_from:
        query = query.filter(StockHistory.created_at >= date_from)
    if date_to:
        query = query.filter(StockHistory.created_at <= date_to + " 23:59:59")

    records = query.order_by(StockHistory.created_at.desc()).all()
    return render_template("warehouse_history_global.html",
                           records=records, q=q, op_type=op_type,
                           date_from=date_from, date_to=date_to)


@bp.route("/<int:part_id>/delete", methods=["POST"])
def part_delete(part_id):
    part = Part.query.get_or_404(part_id)
    try:
        from .models import log_stock_operation
        if part.quantity > 0:
            log_stock_operation(part.id, part.name, "WRITE_OFF", -part.quantity)
        db.session.delete(part)
        db.session.commit()
        flash("Деталь удалена", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Не удалось удалить деталь: {e}", "danger")
    return redirect(url_for("warehouse.parts_list"))
