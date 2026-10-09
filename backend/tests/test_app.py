from backend.app import create_app
from backend.config import TestingConfig
from backend.routes.pages import PAGE_ROUTES


def test_create_app_with_testing_config():
    app = create_app(TestingConfig)
    assert app.testing is True
    assert app.config["ENV_NAME"] == "testing"
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite+pysqlite:///:memory:"


def test_all_19_page_routes_exist(client):
    assert len(PAGE_ROUTES) == 19
    for route in PAGE_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route


def test_liveness(client):
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.get_json()["status"] == "live"


def test_readiness_with_database(client):
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["checks"]["database"]["status"] == "ok"
    assert payload["checks"]["contracts"]["status"] == "ok"
    assert "uri" not in str(payload).lower()


def test_unified_not_found(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {
        "error": {"code": "NOT_FOUND", "message": "The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.", "details": {}}
    }


def test_mock_dashboard_is_not_exposed_and_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/dashboard").status_code == 404
