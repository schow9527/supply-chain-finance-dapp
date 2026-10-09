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
    assert web["numInstances"] == 1
    assert web["disk"] == {
        "name": "invoice-pdf-data",
        "mountPath": "/opt/render/project/src/uploads",
        "sizeGB": 1,
    }
    assert "disk" not in worker and "scaling" not in web
    for service in (web, worker):
        env = {item["key"]: item for item in service["envVars"]}
        assert env["DATABASE_URL"]["fromDatabase"]["name"] == "supply-chain-finance-db"
        assert env["WEB3_PROVIDER_URI"] == {"key": "WEB3_PROVIDER_URI", "sync": False}
    web_env = {item["key"]: item.get("value") for item in web["envVars"]}
    worker_env = {item["key"]: item.get("value") for item in worker["envVars"]}
    assert web_env["EVENT_SYNC_ENABLED"] == "false"
    assert worker_env["EVENT_SYNC_ENABLED"] == "true"
    assert web_env["STORAGE_BACKEND"] == "render_disk"
    assert web_env["PROCESS_ROLE"] == "web"
    assert worker_env["PROCESS_ROLE"] == "worker"
    assert web_env["RENDER_DISK_MOUNT_PATH"] == "/opt/render/project/src/uploads"
    assert web_env["UPLOAD_FOLDER"] == "/opt/render/project/src/uploads"
    assert worker_env["STORAGE_BACKEND"] == "disabled"
    web_items = {item["key"]: item for item in web["envVars"]}
    for key in ("WEB3_PROVIDER_URI",):
        assert web_items[key].get("sync") is False
        assert "value" not in web_items[key]
    assert not any(key.startswith("S3_") for key in web_items)
    assert "postgresql://" not in raw and "postgres://" not in raw
