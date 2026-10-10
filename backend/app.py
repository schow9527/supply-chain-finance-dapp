"""Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from backend.config import configure_app
from backend.errors import register_error_handlers
from backend.extensions import cors, db, migrate
from backend.routes.health import health_bp
from backend.routes.auth import auth_bp
from backend.routes.enterprises import enterprises_bp
from backend.routes.invoices import invoices_bp
from backend.routes.queries import queries_bp
from backend.routes.pages import pages_bp
from backend.sync.cli import register_sync_commands

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app(config_object=None) -> Flask:
    """Create an application without connecting to external services."""
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "frontend" / "templates"),
        static_folder=str(BASE_DIR / "frontend" / "static"),
        static_url_path="/static",
    )
    configure_app(app, config_object)
    db.init_app(app)
    # Register model metadata without performing database I/O.
    from backend import models  # noqa: F401

    migrate.init_app(app, db, directory=str(BASE_DIR / "backend" / "migrations"))
    cors.init_app(app)
    app.register_blueprint(pages_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(enterprises_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(queries_bp)
    register_error_handlers(app)
    register_sync_commands(app)

    # Automatically initialize tables for SQLite development/Render deployments
    if not app.config.get("TESTING"):
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if uri.startswith("sqlite"):
            with app.app_context():
                try:
                    from flask_migrate import upgrade
                    upgrade(directory=str(BASE_DIR / "backend" / "migrations"))
                except Exception:
                    db.create_all()

    return app


# WSGI entrypoint; extension initialization performs no database/RPC I/O.
app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=app.config.get("DEBUG", False),
    )
