import web3

from backend.app import create_app
from backend.config import TestingConfig, ZERO_ADDRESS
from backend.extensions import db
from backend.models import SyncState
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
    assert response.status_code == 503
    payload = response.get_json()
    assert payload["status"] == "degraded"
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
    assert response.status_code == 503
    storage = response.get_json()["checks"]["storage"]
    assert storage["backend"] == "render_disk"
    assert storage["status"] == "ok"
    assert storage["free_space"] in {"adequate", "healthy"}
    assert str(tmp_path) not in response.get_data(as_text=True)


def test_readiness_returns_200_when_rpc_and_sync_are_healthy(
    client, app, monkeypatch
):
    class FakeWeb3:
        HTTPProvider = staticmethod(lambda *_args, **_kwargs: object())

        def __init__(self, _provider):
            self.eth = type("Eth", (), {"chain_id": 11155111, "block_number": 200})()

    monkeypatch.setattr(web3, "Web3", FakeWeb3)
    app.config.update(
        RPC_HEALTHCHECK_ENABLED=True,
        RPC_HEALTHCHECK_CACHE_TTL=0,
        WEB3_PROVIDER_URI="https://sepolia.example.invalid",
        SYNC_MAX_LAG_BLOCKS=12,
    )
    db.session.add(SyncState(
        chain_id=11155111,
        contract_address=ZERO_ADDRESS,
        contract_name="all-contracts",
        last_synced_block=199,
        latest_chain_block=199,
        status="healthy",
    ))
    db.session.commit()

    response = client.get("/api/health/ready")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "ready"
    assert payload["checks"]["sync_lag_blocks"] == 1


def test_readiness_uses_live_chain_head_and_detects_stalled_sync(
    client, app, monkeypatch
):
    class FakeWeb3:
        HTTPProvider = staticmethod(lambda *_args, **_kwargs: object())

        def __init__(self, _provider):
            self.eth = type("Eth", (), {"chain_id": 11155111, "block_number": 200})()

    monkeypatch.setattr(web3, "Web3", FakeWeb3)
    app.config.update(
        RPC_HEALTHCHECK_ENABLED=True,
        RPC_HEALTHCHECK_CACHE_TTL=0,
        WEB3_PROVIDER_URI="https://sepolia.example.invalid",
        SYNC_MAX_LAG_BLOCKS=12,
    )
    db.session.add(SyncState(
        chain_id=11155111,
        contract_address=ZERO_ADDRESS,
        contract_name="all-contracts",
        last_synced_block=100,
        latest_chain_block=101,
        status="healthy",
    ))
    db.session.commit()

    response = client.get("/api/health/ready")
    payload = response.get_json()

    assert response.status_code == 503
    assert payload["status"] == "degraded"
    assert payload["checks"]["rpc"]["latest_chain_block"] == 200
    assert payload["checks"]["latest_chain_block"] == 200
    assert payload["checks"]["sync_lag_blocks"] == 100
    assert payload["checks"]["event_sync"]["error"] == "SYNC_LAG_EXCEEDED"


def test_readiness_reports_rpc_chain_mismatch(client, app, monkeypatch):
    class FakeWeb3:
        HTTPProvider = staticmethod(lambda *_args, **_kwargs: object())

        def __init__(self, _provider):
            self.eth = type("Eth", (), {"chain_id": 1, "block_number": 26000000})()

    monkeypatch.setattr(web3, "Web3", FakeWeb3)
    app.config.update(
        RPC_HEALTHCHECK_ENABLED=True,
        RPC_HEALTHCHECK_CACHE_TTL=0,
        WEB3_PROVIDER_URI="https://mainnet.example.invalid",
    )

    response = client.get("/api/health/ready")
    payload = response.get_json()

    assert response.status_code == 503
    assert payload["status"] == "degraded"
    assert payload["checks"]["rpc"]["status"] == "invalid"
    assert payload["checks"]["rpc"]["error"] == "RPC_CHAIN_MISMATCH"
    assert payload["checks"]["rpc"]["actual_chain_id"] == 1
    assert payload["checks"]["latest_chain_block"] is None


def test_unified_not_found(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {
        "error": {"code": "NOT_FOUND", "message": "The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.", "details": {}}
    }


def test_me_and_real_dashboard_require_auth(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/dashboard").status_code == 401
