from backend.app import create_app
from backend.config import TestingConfig
from backend.routes.pages import PAGE_ROUTES
from backend.storage import RenderDiskStorage


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
    assert payload["checks"]["event_sync"]["status"] == "degraded"
    assert payload["checks"]["last_synced_block"] is None
    assert "uri" not in str(payload).lower()


def test_readiness_storage_failure_is_critical_even_when_rpc_is_temporary(client, app):
    class UnhealthyStorage:
        def health_check(self):
            return False

    app.config.update(
        STORAGE_SERVICE=UnhealthyStorage(),
        RPC_HEALTHCHECK_ENABLED=True,
        WEB3_PROVIDER_URI="https://unavailable.example.invalid",
        RPC_HEALTHCHECK_TIMEOUT=0.01,
    )
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    payload = response.get_json()
    assert payload["error"]["details"]["status"] == "unavailable"
    checks = payload["error"]["details"]["checks"]
    assert checks["storage"]["status"] == "unavailable"
    assert checks["rpc"]["status"] == "unavailable"


def test_readiness_render_disk_is_healthy_without_exposing_path(client, app, tmp_path):
    app.config.update(
        STORAGE_BACKEND="render_disk",
        STORAGE_SERVICE=RenderDiskStorage(tmp_path, tmp_path, min_free_bytes=1),
    )
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    storage = response.get_json()["checks"]["storage"]
    assert storage["backend"] == "render_disk"
    assert storage["status"] == "ok"
    assert storage["free_space"] in {"adequate", "healthy"}
    assert str(tmp_path) not in response.get_data(as_text=True)


def test_unified_not_found(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {
        "error": {"code": "NOT_FOUND", "message": "The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.", "details": {}}
    }


def test_me_and_real_dashboard_require_auth(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/dashboard").status_code == 401
