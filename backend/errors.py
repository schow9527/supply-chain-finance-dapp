"""Consistent JSON errors without leaking internal exception details."""

from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException

from backend.extensions import db

ERROR_CODES = {
    400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN",
    404: "NOT_FOUND", 409: "CONFLICT", 413: "FILE_TOO_LARGE",
    422: "UNPROCESSABLE_ENTITY", 500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def error_response(status: int, message: str, details=None):
    return jsonify({"error": {"code": ERROR_CODES.get(status, "HTTP_ERROR"),
                               "message": message, "details": details or {}}}), status


def api_error(code: str, message: str, status: int, details=None):
    """Return a stable business error while preserving the common envelope."""
    return jsonify({"error": {"code": code, "message": message,
                               "details": details or {}}}), status


def register_error_handlers(app) -> None:
    for status in ERROR_CODES:
        app.register_error_handler(status, _handle_http_error)
    app.register_error_handler(Exception, _handle_unexpected_error)


def _handle_http_error(error):
    status = error.code if isinstance(error, HTTPException) else 500
    if status >= 500:
        db.session.rollback()
    message = "An internal server error occurred." if status == 500 else getattr(
        error, "description", "Request failed."
    )
    return error_response(status, message)


def _handle_unexpected_error(error):
    db.session.rollback()
    current_app.logger.exception("Unhandled application error")
    return error_response(500, "An internal server error occurred.")
