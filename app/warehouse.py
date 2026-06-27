from flask import Blueprint, render_template, request, redirect, url_for, flash
from .extensions import db
from .models import Part

bp = Blueprint("warehouse", __name__, url_prefix="/warehouse")


@bp.route("/")
def parts_list():
    parts = Part.query.order_by(Part.name).all()
    return render_template("warehouse_list.html", parts=parts)


@bp.route("/add", methods=["GET", "POST"])
def part_add():
    if request.method == "POST":
        try:
            part = Part(
                name=request.form["name"].strip(),
                price=float(request.form["price"]),
                location=request.form.get("location", "На складе").strip(),
            )
            db.session.add(part)
            db.session.commit()
            flash(f"Деталь «{part.name}» добавлена", "success")
            return redirect(url_for("warehouse.parts_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при добавлении детали: {e}", "danger")
    return render_template("warehouse_form.html", part=None)


@bp.route("/<int:part_id>/edit", methods=["GET", "POST"])
def part_edit(part_id):
    part = Part.query.get_or_404(part_id)
    if request.method == "POST":
        try:
            part.name = request.form["name"].strip()
            part.price = float(request.form["price"])
            part.location = request.form.get("location", "На складе").strip()
            db.session.commit()
            flash("Деталь обновлена", "success")
            return redirect(url_for("warehouse.parts_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при обновлении детали: {e}", "danger")
    return render_template("warehouse_form.html", part=part)


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
