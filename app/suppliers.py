from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import or_
from .extensions import db
from .models import Supplier, Attribute, SupplierAttribute

suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@suppliers_bp.route("/")
def list_suppliers():
    q = request.args.get("q", "").strip()
    query = Supplier.query
    if q:
        query = query.filter(
            or_(
                Supplier.name.ilike(f"%{q}%"),
                Supplier.org_number.ilike(f"%{q}%"),
                Supplier.address.ilike(f"%{q}%"),
                Supplier.phone.ilike(f"%{q}%"),
            )
        )
    suppliers = query.order_by(Supplier.name).all()
    return render_template("supplier_list.html", suppliers=suppliers, q=q)


@suppliers_bp.route("/add", methods=["GET", "POST"])
def add_supplier():
    if request.method == "POST":
        try:
            supplier = Supplier(
                name=request.form["name"].strip(),
                org_number=request.form.get("org_number", "").strip(),
                address=request.form.get("address", "").strip(),
                work_time=request.form.get("work_time", "").strip(),
                phone=request.form.get("phone", "").strip(),
            )
            db.session.add(supplier)
            db.session.flush()

            # Сохранение атрибутов поставщика
            for attr in Attribute.query.filter_by(entity_type="supplier").all():
                value = request.form.get(f"supattr_{attr.id}", "").strip()
                if value:
                    db.session.add(SupplierAttribute(supplier_id=supplier.id, attribute_id=attr.id, value=value))

            db.session.commit()
            flash("Поставщик добавлен", "success")
            return redirect(url_for("suppliers.list_suppliers"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка: {e}", "danger")

    supplier_attributes = Attribute.query.filter_by(entity_type="supplier").all()
    return render_template("supplier_form.html", supplier=None, supplier_attributes=supplier_attributes, supplier_attrs={})


@suppliers_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == "POST":
        try:
            supplier.name = request.form["name"].strip()
            supplier.org_number = request.form.get("org_number", "").strip()
            supplier.address = request.form.get("address", "").strip()
            supplier.work_time = request.form.get("work_time", "").strip()
            supplier.phone = request.form.get("phone", "").strip()

            # Сохранение атрибутов поставщика
            SupplierAttribute.query.filter_by(supplier_id=supplier.id).delete()
            for attr in Attribute.query.filter_by(entity_type="supplier").all():
                value = request.form.get(f"supattr_{attr.id}", "").strip()
                if value:
                    db.session.add(SupplierAttribute(supplier_id=supplier.id, attribute_id=attr.id, value=value))

            db.session.commit()
            flash("Поставщик обновлён", "success")
            return redirect(url_for("suppliers.list_suppliers"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка: {e}", "danger")

    supplier_attributes = Attribute.query.filter_by(entity_type="supplier").all()
    supplier_attrs = {sa.attribute_id: sa.value for sa in supplier.attributes}
    return render_template("supplier_form.html", supplier=supplier, supplier_attributes=supplier_attributes, supplier_attrs=supplier_attrs)


@suppliers_bp.route("/<int:supplier_id>/delete", methods=["POST"])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    try:
        db.session.delete(supplier)
        db.session.commit()
        flash("Поставщик удалён", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Не удалось удалить: {e}", "danger")
    return redirect(url_for("suppliers.list_suppliers"))
