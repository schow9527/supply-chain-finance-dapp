"""Existing server-rendered page routes."""

from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)
PAGE_ROUTES = {
    "/": "index.html", "/register": "register.html",
    "/supplier/dashboard": "supplier/dashboard.html",
    "/supplier/upload_invoice": "supplier/upload_invoice.html",
    "/supplier/invoices": "supplier/invoices.html",
    "/supplier/receivables": "supplier/receivables.html",
    "/supplier/financing": "supplier/financing.html",
    "/core_enterprise/dashboard": "core_enterprise/dashboard.html",
    "/core_enterprise/invoices_pending": "core_enterprise/invoices_pending.html",
    "/core_enterprise/payables": "core_enterprise/payables.html",
    "/financier/dashboard": "financier/dashboard.html",
    "/financier/market": "financier/market.html",
    "/financier/portfolio": "financier/portfolio.html",
    "/auditor/overview": "auditor/overview.html",
    "/auditor/tracing": "auditor/tracing.html",
    "/admin/registrations": "admin/registrations.html",
    "/admin/system": "admin/system.html",
    "/common/transactions": "common/transactions.html",
    "/common/events": "common/events.html",
}


def _register_page(path, template):
    endpoint = "page_" + (path.strip("/") or "index").replace("/", "_")

    def view():
        return render_template(template)

    pages_bp.add_url_rule(path, endpoint, view)


for _path, _template in PAGE_ROUTES.items():
    _register_page(_path, _template)
