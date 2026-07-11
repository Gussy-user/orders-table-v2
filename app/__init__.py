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

        # Add article column to part table if it doesn't exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('part')]
        if 'article' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE part ADD COLUMN article VARCHAR(60)'))
                conn.commit()
        if 'purchase_price' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE part ADD COLUMN purchase_price FLOAT DEFAULT 0'))
                conn.commit()
        if 'quantity' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE part ADD COLUMN quantity INTEGER DEFAULT 0'))
                conn.commit()

        # Add prepayment column to order table if it doesn't exist
        columns = [col['name'] for col in inspector.get_columns('order')]
        if 'prepayment' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE "order" ADD COLUMN prepayment FLOAT DEFAULT 0'))
                conn.commit()
        if 'is_archived_manually' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE "order" ADD COLUMN is_archived_manually BOOLEAN DEFAULT 0'))
                conn.commit()

        # Add messenger fields to client table if they don't exist
        columns = [col['name'] for col in inspector.get_columns('client')]
        for col_name in ['telegram', 'whatsapp', 'max_account']:
            if col_name not in columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text(f'ALTER TABLE client ADD COLUMN {col_name} VARCHAR(120)'))
                    conn.commit()

        # Add entity_type to attribute table if it doesn't exist
        tables = inspector.get_table_names()
        if 'attribute' in tables:
            columns = [col['name'] for col in inspector.get_columns('attribute')]
            if 'entity_type' not in columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE attribute ADD COLUMN entity_type VARCHAR(20) DEFAULT 'client'"))
                    conn.commit()

        # Create stock_history table if it doesn't exist
        if 'stock_history' not in tables:
            with db.engine.connect() as conn:
                conn.execute(db.text("""
                    CREATE TABLE stock_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER REFERENCES part(id) ON DELETE SET NULL,
                        product_name VARCHAR(120) NOT NULL DEFAULT '',
                        operation_type VARCHAR(20) NOT NULL,
                        quantity_change INTEGER NOT NULL,
                        details TEXT,
                        order_id INTEGER REFERENCES "order"(id),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
        else:
            sh_columns = [col['name'] for col in inspector.get_columns('stock_history')]
            if 'product_name' not in sh_columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE stock_history ADD COLUMN product_name VARCHAR(120) NOT NULL DEFAULT ''"))
                    conn.commit()
            if 'details' not in sh_columns:
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE stock_history ADD COLUMN details TEXT"))
                    conn.commit()
            # Recreate table with proper FK constraint
            with db.engine.connect() as conn:
                fk_info = conn.execute(db.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='stock_history'")).fetchone()
                if fk_info and 'ON DELETE SET NULL' not in fk_info[0]:
                    conn.execute(db.text("ALTER TABLE stock_history RENAME TO stock_history_old"))
                    conn.execute(db.text("""
                        CREATE TABLE stock_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            product_id INTEGER REFERENCES part(id) ON DELETE SET NULL,
                            product_name VARCHAR(120) NOT NULL DEFAULT '',
                            operation_type VARCHAR(20) NOT NULL,
                            quantity_change INTEGER NOT NULL,
                            details TEXT,
                            order_id INTEGER REFERENCES "order"(id),
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(db.text("INSERT INTO stock_history (id, product_id, product_name, operation_type, quantity_change, details, order_id, created_at) SELECT id, product_id, COALESCE(product_name, ''), operation_type, quantity_change, details, order_id, created_at FROM stock_history_old"))
                    conn.execute(db.text("DROP TABLE stock_history_old"))
                    conn.commit()

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
