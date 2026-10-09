from pathlib import Path

import yaml


def test_render_blueprint_has_safe_web_worker_and_database():
    root = Path(__file__).resolve().parents[2]
    raw = (root / "render.yaml").read_text(encoding="utf-8")
    blueprint = yaml.safe_load(raw)
    services = {item["type"]: item for item in blueprint["services"]}
    web = services["web"]
    worker = services["worker"]
    assert blueprint["databases"][0]["plan"] == "0.1c-256mb"
    assert web["plan"] == worker["plan"] == "0.5c-512mb"
    assert web["region"] == worker["region"] == "singapore"
    assert web["startCommand"] == "gunicorn app:app"
    assert worker["startCommand"] == "python -m backend.worker"
    assert web["preDeployCommand"] == "flask --app app:app db upgrade"
    assert "db upgrade" not in web["buildCommand"]
    assert "preDeployCommand" not in worker
    assert web["healthCheckPath"] == "/api/health/ready"
    for service in (web, worker):
        env = {item["key"]: item for item in service["envVars"]}
        assert env["DATABASE_URL"]["fromDatabase"]["name"] == "supply-chain-finance-db"
        assert env["WEB3_PROVIDER_URI"] == {"key": "WEB3_PROVIDER_URI", "sync": False}
    web_env = {item["key"]: item.get("value") for item in web["envVars"]}
    worker_env = {item["key"]: item.get("value") for item in worker["envVars"]}
    assert web_env["EVENT_SYNC_ENABLED"] == "false"
    assert worker_env["EVENT_SYNC_ENABLED"] == "true"
    assert web_env["STORAGE_BACKEND"] == "s3"
    web_items = {item["key"]: item for item in web["envVars"]}
    for key in ("WEB3_PROVIDER_URI", "S3_ENDPOINT_URL", "S3_REGION", "S3_BUCKET",
                "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        assert web_items[key].get("sync") is False
        assert "value" not in web_items[key]
    assert "postgresql://" not in raw and "postgres://" not in raw
