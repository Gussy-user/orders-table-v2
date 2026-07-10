from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import or_
from .extensions import db
from .models import Part, Attribute, PartAttribute

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
            part.name = request.form["name"].strip()
            part.article = request.form.get("article", "").strip() or None
            part.quantity = int(request.form.get("quantity", 0) or 0)
            part.price = float(request.form["price"])
            part.purchase_price = float(request.form.get("purchase_price", 0) or 0)
            part.location = request.form.get("location", "На складе").strip()

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


@bp.route("/<int:part_id>/delete", methods=["POST"])
def part_delete(part_id):
    part = Part.query.get_or_404(part_id)
    try:
        db.session.delete(part)
        db.session.commit()
        flash("Деталь удалена", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Не удалось удалить деталь: {e}", "danger")
    return redirect(url_for("warehouse.parts_list"))
