import os
from pathlib import Path
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from backend.config import Config

BASE_DIR = Path(__file__).resolve().parent.parent

def create_app():
    frontend_templates = BASE_DIR / "frontend" / "templates"
    frontend_static = BASE_DIR / "frontend" / "static"

    app = Flask(
        __name__,
        template_folder=str(frontend_templates),
        static_folder=str(frontend_static),
        static_url_path="/static"
    )
    app.config.from_object(Config)
    CORS(app)

    # Global Unified Error Handler (PRD section 7 requirement)
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Resource not found"}}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Internal server error occurred"}}), 500

    # Basic routes
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health")
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Supply Chain Finance DApp API",
            "version": "1.0.0"
        })

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
