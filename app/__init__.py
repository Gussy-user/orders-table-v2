import os
from flask import Flask, redirect, url_for, request
from .extensions import db, migrate
from .errors import register_error_handlers
from .utils import data_path


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static")),
        template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates")),
    )
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "orders-table-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{data_path('orders.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes import bp as main_bp
    from .orders import bp as orders_bp
    from .warehouse import bp as warehouse_bp
    from .suppliers import suppliers_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(warehouse_bp)
    app.register_blueprint(suppliers_bp)

    register_error_handlers(app)

    with app.app_context():
        db.create_all()

        from .models import Settings, License
        if not Settings.query.first():
            db.session.commit()

        # Seed hardcoded license keys if the license table is empty (fresh install)
        if not License.query.first():
            from .seed_keys import ONEPASS_HASHES, MASTER_HASH
            for h in ONEPASS_HASHES:
                db.session.add(License(key=h, key_type="onepass"))
            db.session.add(License(key=MASTER_HASH, key_type="master"))
            db.session.commit()

        from .models import Status, OrderStatus
        for name in ["В работе", "Выдан", "Задержка"]:
            if not Status.query.filter_by(name=name).first():
                db.session.add(Status(name=name))
        for name in ["В работе", "Выдан", "Задержка", "Отменён"]:
            if not OrderStatus.query.filter_by(name=name).first():
                db.session.add(OrderStatus(name=name))
        db.session.commit()

    @app.before_request
    def check_license():
        from .models import Settings
        if not request.endpoint:
            return
        if request.endpoint in ("main.activate", "static"):
            return
        try:
            s = Settings.query.filter_by(key="licensed").first()
            if not s or s.value != "1":
                return redirect(url_for("main.activate"))
        except Exception:
            return redirect(url_for("main.activate"))

    from apscheduler.schedulers.background import BackgroundScheduler
    from .backup import cleanup_old_backups

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(cleanup_old_backups, "interval", hours=24, id="cleanup_backups")
    scheduler.start()

    return app
