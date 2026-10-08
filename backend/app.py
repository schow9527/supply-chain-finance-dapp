import os
from pathlib import Path
from flask import Flask, jsonify, render_template, request
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

    # Global Unified Error Handler (PRD section 7)
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": {"code": "BAD_REQUEST", "message": str(e)}}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Resource not found"}}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Internal server error occurred"}}), 500

    # ==================== Page Routes (19 Views) ====================
    @app.route("/")
    def index_page():
        return render_template("index.html")

    @app.route("/register")
    def register_page():
        return render_template("register.html")

    # Supplier routes
    @app.route("/supplier/dashboard")
    def supplier_dashboard():
        return render_template("supplier/dashboard.html")

    @app.route("/supplier/upload_invoice")
    def supplier_upload_invoice():
        return render_template("supplier/upload_invoice.html")

    @app.route("/supplier/invoices")
    def supplier_invoices():
        return render_template("supplier/invoices.html")

    @app.route("/supplier/receivables")
    def supplier_receivables():
        return render_template("supplier/receivables.html")

    @app.route("/supplier/financing")
    def supplier_financing():
        return render_template("supplier/financing.html")

    # Core Enterprise routes
    @app.route("/core_enterprise/dashboard")
    def core_enterprise_dashboard():
        return render_template("core_enterprise/dashboard.html")

    @app.route("/core_enterprise/invoices_pending")
    def core_enterprise_invoices_pending():
        return render_template("core_enterprise/invoices_pending.html")

    @app.route("/core_enterprise/payables")
    def core_enterprise_payables():
        return render_template("core_enterprise/payables.html")

    # Financier routes
    @app.route("/financier/dashboard")
    def financier_dashboard():
        return render_template("financier/dashboard.html")

    @app.route("/financier/market")
    def financier_market():
        return render_template("financier/market.html")

    @app.route("/financier/portfolio")
    def financier_portfolio():
        return render_template("financier/portfolio.html")

    # Auditor routes
    @app.route("/auditor/overview")
    def auditor_overview():
        return render_template("auditor/overview.html")

    @app.route("/auditor/tracing")
    def auditor_tracing():
        return render_template("auditor/tracing.html")

    # Admin routes
    @app.route("/admin/registrations")
    def admin_registrations():
        return render_template("admin/registrations.html")

    @app.route("/admin/system")
    def admin_system():
        return render_template("admin/system.html")

    # Common routes
    @app.route("/common/transactions")
    def common_transactions():
        return render_template("common/transactions.html")

    @app.route("/common/events")
    def common_events():
        return render_template("common/events.html")

    # ==================== Health & Mock/Stub API Fallbacks ====================
    @app.route("/api/health")
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Supply Chain Finance DApp API",
            "version": "1.0.0"
        })

    @app.route("/api/me")
    def mock_me():
        addr = request.args.get("address", "")
        return jsonify({
            "wallet_address": addr,
            "role": "NONE",
            "enterprise_name": "访客"
        })

    @app.route("/api/dashboard")
    def mock_dashboard():
        return jsonify({
            "receivable_total": "0",
            "pending_invoices_count": 0,
            "financing_active_amount": "0",
            "funded_total_amount": "0"
        })

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
