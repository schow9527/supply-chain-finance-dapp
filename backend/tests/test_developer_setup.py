import json
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]


def test_env_example_matches_current_deployment_and_is_offline_safe():
    example = dotenv_values(ROOT / ".env.example")
    deployment = json.loads(
        (ROOT / "contracts" / "deployments" / "11155111.json").read_text(
            encoding="utf-8"
        )
    )

    assert example["APP_ENV"] == "development"
    assert example["PROCESS_ROLE"] == "web"
    assert example["DATABASE_URL"].startswith("sqlite:")
    assert example["STORAGE_BACKEND"] == "local"
    assert example["EVENT_SYNC_ENABLED"] == "false"
    assert example["WEB3_PROVIDER_URI"] == ""
    assert int(example["CHAIN_ID"]) == deployment["chainId"]
    assert int(example["SYNC_START_BLOCK"]) == deployment["startBlock"]


def test_root_readme_documents_reproducible_and_safe_setup():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    required_instructions = (
        "python -m venv .venv",
        "pip install -r requirements.txt",
        "Copy-Item .env.example .env",
        "flask --app app:app db upgrade",
        "python app.py",
        "pytest backend/tests",
        "npm test",
        "WEB3_PROVIDER_URI",
        "python -m backend.worker",
        "不得写入 `.env.example` 或提交到 Git",
    )
    for instruction in required_instructions:
        assert instruction in readme
