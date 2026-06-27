from flask import render_template


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html", error=error), 404

    @app.errorhandler(500)
    def internal_error(error):
        from .extensions import db
        db.session.rollback()
        return render_template("500.html", error=error), 500
