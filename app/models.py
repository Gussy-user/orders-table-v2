from datetime import datetime
from .extensions import db


class Status(db.Model):
    __tablename__ = "status"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)

    def __repr__(self):
        return f"<Status {self.name}>"


class OrderStatus(db.Model):
    __tablename__ = "order_status"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)

    def __repr__(self):
        return f"<OrderStatus {self.name}>"


class Client(db.Model):
    __tablename__ = "client"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status_id = db.Column(db.Integer, db.ForeignKey("status.id"), nullable=False)
    telegram = db.Column(db.String(120), nullable=True)
    whatsapp = db.Column(db.String(120), nullable=True)
    max_account = db.Column(db.String(120), nullable=True)

    status = db.relationship("Status", backref="clients")
    cars = db.relationship("Car", backref="owner", cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="client", cascade="all, delete-orphan")
    attributes = db.relationship("ClientAttribute", backref="client", cascade="all, delete-orphan")

    @property
    def total_price(self) -> float:
        return sum(o.total_price for o in self.orders if not o.archived)

    def __repr__(self):
        return f"<Client {self.name} ({self.phone})>"


class Car(db.Model):
    __tablename__ = "car"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    vin = db.Column(db.String(30), nullable=False)
    make = db.Column(db.String(60), nullable=False)
    model = db.Column(db.String(60), nullable=False)
    year = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<Car {self.make} {self.model} ({self.vin})>"


class Part(db.Model):
    __tablename__ = "part"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    article = db.Column(db.String(60), nullable=True)
    price = db.Column(db.Float, nullable=False)
    purchase_price = db.Column(db.Float, nullable=True, default=0)
    location = db.Column(db.String(120), nullable=True, default="На складе")

    def __repr__(self):
        return f"<Part {self.name} @ {self.price}>"


class Order(db.Model):
    __tablename__ = "order"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status_id = db.Column(db.Integer, db.ForeignKey("order_status.id"), nullable=False)
    archived = db.Column(db.Boolean, default=False)
    is_archived_manually = db.Column(db.Boolean, default=False)
    payment_status = db.Column(db.String(30), nullable=False, default="Не оплачен")
    prepayment = db.Column(db.Float, nullable=True, default=0)

    status = db.relationship("OrderStatus", backref="orders")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    @property
    def total_price(self) -> float:
        return sum(i.total for i in self.items)

    @property
    def debt(self) -> float:
        return round(self.total_price - (self.prepayment or 0), 2)

    @property
    def status_css(self) -> str:
        return f"status-order-{self.status.name.lower().replace(' ', '-')}" if self.status else ""

    def __repr__(self):
        return f"<Order #{self.order_number} client={self.client_id}>"


class OrderItem(db.Model):
    __tablename__ = "order_item"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey("part.id"), nullable=True)
    part_name = db.Column(db.String(120), nullable=False)
    article = db.Column(db.String(60), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False, default=0)
    item_status = db.Column(db.String(30), nullable=False, default="Ожидается")

    part = db.relationship("Part", backref="order_items")

    @property
    def total(self):
        return self.quantity * self.price

    def __repr__(self):
        return f"<OrderItem {self.part_name} x{self.quantity}>"


class Attribute(db.Model):
    __tablename__ = "attribute"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    values = db.relationship("ClientAttribute", backref="attribute", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Attribute {self.name}>"


class ClientAttribute(db.Model):
    __tablename__ = "client_attribute"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey("attribute.id"), nullable=False)
    value = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<ClientAttribute client={self.client_id} attr={self.attribute_id} value={self.value}>"


class Supplier(db.Model):
    __tablename__ = "supplier"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    org_number = db.Column(db.String(60), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    work_time = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)

    def __repr__(self):
        return f"<Supplier {self.name}>"


class Settings(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=True)

    @staticmethod
    def get(key: str, default: str = "") -> str:
        s = Settings.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key: str, value: str):
        s = Settings.query.filter_by(key=key).first()
        if s:
            s.value = value
        else:
            s = Settings(key=key, value=value)
            db.session.add(s)
        db.session.commit()


class License(db.Model):
    __tablename__ = "license"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    key_type = db.Column(db.String(20), nullable=False)
    used = db.Column(db.Boolean, default=False)
    activated_at = db.Column(db.DateTime, nullable=True)
