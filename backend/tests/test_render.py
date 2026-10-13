from pathlib import Path

import yaml


def test_render_blueprint_has_safe_colocated_web_worker_and_database():
    root = Path(__file__).resolve().parents[2]
    raw = (root / "render.yaml").read_text(encoding="utf-8")
    blueprint = yaml.safe_load(raw)
    assert len(blueprint["services"]) == 1
    web = blueprint["services"][0]
    assert web["type"] == "web"
    assert blueprint["databases"][0]["plan"] == "0.1c-256mb"
    assert web["plan"] == "0.5c-512mb"
    assert web["region"] == "singapore"
    assert web["startCommand"] == "python -m backend.combined"
    assert web["preDeployCommand"] == "flask --app app:app db upgrade"
    assert "db upgrade" not in web["buildCommand"]
    assert web["healthCheckPath"] == "/api/health/ready"
    assert web["numInstances"] == 1
    assert web["disk"] == {
        "name": "invoice-pdf-data",
        "mountPath": "/opt/render/project/src/uploads",
        "sizeGB": 1,
    }
    assert "scaling" not in web
    env = {item["key"]: item for item in web["envVars"]}
    assert env["DATABASE_URL"] == {"key": "DATABASE_URL", "sync": False}
    assert "fromDatabase" not in env["DATABASE_URL"]
    assert "value" not in env["DATABASE_URL"]
    assert env["WEB3_PROVIDER_URI"] == {"key": "WEB3_PROVIDER_URI", "sync": False}
    assert env["SECRET_KEY"] == {"key": "SECRET_KEY", "generateValue": True}
    web_env = {item["key"]: item.get("value") for item in web["envVars"]}
    assert web_env["EVENT_SYNC_ENABLED"] == "false"
    assert web_env["APP_ENV"] == "production"
    assert web_env["EVENT_SYNC_BATCH_SIZE"] == "100"
    assert web_env["SYNC_POLL_INTERVAL"] == "12"
    assert web_env["STORAGE_BACKEND"] == "render_disk"
    assert web_env["PROCESS_ROLE"] == "web"
    assert web_env["RENDER_DISK_MOUNT_PATH"] == "/opt/render/project/src/uploads"
    assert web_env["UPLOAD_FOLDER"] == "/opt/render/project/src/uploads"
    web_items = {item["key"]: item for item in web["envVars"]}
    for key in ("WEB3_PROVIDER_URI", "DATABASE_URL"):
        assert web_items[key].get("sync") is False
        assert "value" not in web_items[key]
    assert not any(key.startswith("S3_") for key in web_items)
    assert "postgresql://" not in raw and "postgres://" not in raw
    assert "property: connectionString" not in raw
