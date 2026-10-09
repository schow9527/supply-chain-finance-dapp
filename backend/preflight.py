"""Read-only production preflight checks with deliberately redacted output."""

from __future__ import annotations

import json
from dataclasses import dataclass

from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url

from backend.config import (
    BASE_DIR, CONTRACT_NAMES, DEFAULT_SECRET_KEY, DEPLOYMENT_FILE,
    EXAMPLE_SECRET_KEY, ZERO_ADDRESS,
)
from backend.extensions import db
from backend.models import SyncState
from backend.services.addresses import (
    ContractAddressError, canonical_address, masked_address, rpc_checksum_address,
)
from backend.storage import get_storage
from backend.sync.registry import ABI_DIR


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    critical: bool = True

    @property
    def passed(self) -> bool:
        return self.status in {"PASS", "NOT_STARTED"}


def _safe_database_label(uri: str) -> str:
    try:
        url = make_url(uri)
        return f"{url.drivername}://{url.host or 'local'}/***"
    except Exception:
        return "invalid://***/***"


def _migration_check() -> Check:
    try:
        alembic = AlembicConfig(str(BASE_DIR / "backend" / "migrations" / "alembic.ini"))
        alembic.set_main_option("script_location", str(BASE_DIR / "backend" / "migrations"))
        head = ScriptDirectory.from_config(alembic).get_current_head()
        with db.engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current = context.get_current_revision()
            if current != head:
                return Check("MIGRATIONS", "FAIL", "current revision is not head")
            drift = compare_metadata(context, db.metadata)
        return Check("MIGRATIONS", "PASS" if not drift else "FAIL",
                     "no drift" if not drift else "schema drift detected")
    except Exception:
        return Check("MIGRATIONS", "FAIL", "migration state unavailable")


def _database_checks(app) -> list[Check]:
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    label = _safe_database_label(uri)
    try:
        if make_url(uri).get_backend_name() != "postgresql":
            return [Check("DATABASE", "FAIL", f"{label} is not PostgreSQL"),
                    Check("MIGRATIONS", "FAIL", "requires PostgreSQL connection")]
        db.session.execute(text("SELECT 1"))
        return [Check("DATABASE", "PASS", label), _migration_check()]
    except Exception:
        db.session.rollback()
        return [Check("DATABASE", "FAIL", f"{label} is unavailable"),
                Check("MIGRATIONS", "FAIL", "database unavailable")]


def _chain_checks(app) -> list[Check]:
    uri = app.config.get("WEB3_PROVIDER_URI", "")
    if not uri:
        return [
            Check("CHAIN_ID", "FAIL", "REAL_SEPOLIA_RPC_NOT_CONFIGURED"),
            Check("CONTRACTS", "FAIL", "RPC not configured"),
            Check("CONTRACT_LINKS", "FAIL", "RPC not configured"),
        ]
    from web3 import Web3
    web3 = app.config.get("PREFLIGHT_WEB3") or Web3(
        Web3.HTTPProvider(uri, request_kwargs={"timeout": 10})
    )
    try:
        chain_id = int(web3.eth.chain_id)
        latest = int(web3.eth.block_number)
    except Exception as exc:
        return [Check("CHAIN_ID", "FAIL", f"RPC unavailable ({type(exc).__name__})"),
                Check("CONTRACTS", "FAIL", "not checked because RPC is unavailable"),
                Check("CONTRACT_LINKS", "FAIL", "not checked because RPC is unavailable")]
    if chain_id != 11155111:
        return [Check("CHAIN_ID", "FAIL", f"chain_id={chain_id}"),
                Check("CONTRACTS", "FAIL", "not checked on wrong chain"),
                Check("CONTRACT_LINKS", "FAIL", "not checked on wrong chain")]

    chain_check = Check("CHAIN_ID", "PASS", f"chain_id={chain_id} latest={latest}")
    try:
        deployment = json.loads(DEPLOYMENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return [chain_check, Check("CONTRACTS", "FAIL", "deployment manifest unavailable"),
                Check("CONTRACT_LINKS", "FAIL", "deployment manifest unavailable")]
    if latest < int(deployment["startBlock"]):
        return [chain_check, Check("CONTRACTS", "FAIL", "latest block precedes deployment"),
                Check("CONTRACT_LINKS", "FAIL", "deployment block unavailable")]

    contracts = {}
    details = []
    contracts_ok = True
    for name in CONTRACT_NAMES:
        raw_address = app.config.get("CONTRACT_ADDRESSES", {}).get(name, "")
        try:
            address = rpc_checksum_address(raw_address, name)
            masked = masked_address(address)
            expected = canonical_address(deployment.get(name, ""), name)
            if canonical_address(raw_address, name) != expected:
                contracts_ok = False
                details.append(f"{name}={masked}:MANIFEST_MISMATCH")
                continue
        except ContractAddressError as exc:
            contracts_ok = False
            details.append(str(exc))
            continue
        try:
            code = web3.eth.get_code(address)
            if not code or code.hex() in {"", "0x", "00", "0x00"}:
                contracts_ok = False
                details.append(f"{name}={masked}:BYTECODE_MISSING")
                continue
            abi = json.loads((ABI_DIR / f"{name}.json").read_text(encoding="utf-8"))
            contracts[name] = web3.eth.contract(address=address, abi=abi)
            details.append(f"{name}={masked}:BYTECODE_PRESENT")
        except Exception as exc:
            contracts_ok = False
            details.append(f"{name}={masked}:RPC_ERROR_{type(exc).__name__}")

    if not contracts_ok:
        return [chain_check, Check("CONTRACTS", "FAIL", "; ".join(details)),
                Check("CONTRACT_LINKS", "FAIL", "not checked due contract failures")]

    name = "contract"
    function = "view"
    try:
        admin = rpc_checksum_address(deployment["admin"], "DeploymentAdmin")
        view_calls = {
            "RoleManager": [("paused", ()), ("isRegistered", (admin,)), ("roleOf", (admin,))],
            "InvoiceRegistry": [("invoiceCount", ())],
            "FinancingPool": [("requestCount", ()), ("quoteCount", ())],
            "MockStablecoin": [("decimals", ()), ("symbol", ())],
            "ReceivableToken": [("roleManager", ()), ("invoiceRegistry", ()),
                                ("financingPool", ())],
        }
        for name, calls in view_calls.items():
            for function, args in calls:
                getattr(contracts[name].functions, function)(*args).call()
    except Exception as exc:
        return [chain_check,
                Check("CONTRACTS", "FAIL",
                      f"{name}.{function}:VIEW_ERROR_{type(exc).__name__}; " + "; ".join(details)),
                Check("CONTRACT_LINKS", "FAIL", "not checked due view failure")]

    contracts_check = Check("CONTRACTS", "PASS", "; ".join(details))
    owner = "contract"
    function = "link"
    try:
        links = [
            ("InvoiceRegistry", "receivableToken", "ReceivableToken"),
            ("FinancingPool", "receivableToken", "ReceivableToken"),
            ("FinancingPool", "stablecoin", "MockStablecoin"),
            ("ReceivableToken", "invoiceRegistry", "InvoiceRegistry"),
            ("ReceivableToken", "financingPool", "FinancingPool"),
        ]
        for owner, function, target in links:
            actual = getattr(contracts[owner].functions, function)().call()
            actual_normalized = canonical_address(str(actual), f"{owner}.{function}")
            expected = canonical_address(app.config["CONTRACT_ADDRESSES"][target], target)
            if actual_normalized != expected:
                return [chain_check, contracts_check,
                        Check("CONTRACT_LINKS", "FAIL", f"{owner}.{function} mismatch")]
        return [chain_check, contracts_check,
                Check("CONTRACT_LINKS", "PASS", "five references")]
    except Exception as exc:
        return [chain_check, contracts_check,
                Check("CONTRACT_LINKS", "FAIL",
                      f"{owner}.{function}:LINK_ERROR_{type(exc).__name__}")]


def _storage_check(app) -> Check:
    backend = app.config.get("STORAGE_BACKEND", "unknown")
    try:
        storage = get_storage()
        if hasattr(storage, "health_details"):
            details = storage.health_details()
            return Check("STORAGE", "PASS" if details["status"] == "ok" else "FAIL",
                         f"backend={backend} free_space={details['free_space']}")
        return Check("STORAGE", "PASS" if storage.health_check() else "FAIL",
                     f"backend={backend}")
    except Exception:
        return Check("STORAGE", "FAIL", f"backend={backend}")


def _sync_checks(app) -> list[Check]:
    try:
        cursor = SyncState.query.filter_by(
            chain_id=app.config.get("CHAIN_ID"), contract_address=ZERO_ADDRESS
        ).first()
        if cursor is None:
            return [Check("SYNC_STATE", "NOT_STARTED", "no cursor", critical=False),
                    Check("SYNC_LAG", "WARN", "not available", critical=False)]
        lag = (max(0, cursor.latest_chain_block - cursor.last_synced_block)
               if cursor.latest_chain_block is not None else None)
        lag_status = "PASS" if lag is not None and lag <= int(
            app.config.get("SYNC_LAG_WARN_BLOCKS", 100)
        ) else "WARN"
        return [
            Check("SYNC_STATE", "PASS",
                  f"last_synced_block={cursor.last_synced_block} status={cursor.status}",
                  critical=False),
            Check("SYNC_LAG", lag_status,
                  f"blocks={lag}" if lag is not None else "not available", critical=False),
        ]
    except Exception:
        return [Check("SYNC_STATE", "NOT_STARTED", "state unavailable", critical=False),
                Check("SYNC_LAG", "WARN", "state unavailable", critical=False)]


def _common_checks(app, role: str) -> list[Check]:
    secret = app.config.get("SECRET_KEY")
    secret_ok = secret not in {None, "", DEFAULT_SECRET_KEY, EXAMPLE_SECRET_KEY}
    return [
        Check("CONFIG", "PASS" if app.config.get("ENV_NAME") == "production" else "FAIL",
              f"mode={app.config.get('ENV_NAME', 'unknown')}"),
        Check("PROCESS_ROLE", "PASS" if role in {"web", "worker"} else "FAIL",
              f"role={role}"),
        Check("DEBUG", "PASS" if not app.config.get("DEBUG") and not app.config.get("TESTING") else "FAIL",
              "disabled" if not app.config.get("DEBUG") else "enabled"),
        Check("SESSION_SECRET", "PASS" if secret_ok else "FAIL",
              "configured" if secret_ok else "default-or-missing"),
        Check("CONTRACT_CONFIG", "PASS" if DEPLOYMENT_FILE.is_file() else "FAIL",
              "deployment file present" if DEPLOYMENT_FILE.is_file() else "deployment file missing"),
    ]


def collect_preflight(app, role: str | None = None) -> list[Check]:
    role = (role or app.config.get("PROCESS_ROLE") or
            app.config.get("PROCESS_TYPE", "web")).lower()
    checks = _common_checks(app, role)
    checks.extend(_database_checks(app))
    if role == "web":
        checks.append(_storage_check(app))
    elif role == "worker":
        checks.extend(_chain_checks(app))
        checks.extend(_sync_checks(app))
    checks.append(Check("SECRETS_REDACTED", "PASS", "sensitive values omitted"))
    return checks


def collect_post_deploy(app) -> list[Check]:
    """Read-only combined verification for a deployed production environment."""
    checks = _common_checks(app, app.config.get("PROCESS_ROLE", "web"))
    checks.extend(_database_checks(app))
    checks.append(_storage_check(app))
    checks.extend(_chain_checks(app))
    checks.extend(_sync_checks(app))
    try:
        response = app.test_client().get("/api/health/ready")
        payload = response.get_json(silent=True) or {}
        public_status = payload.get("status") or payload.get("error", {}).get(
            "details", {}
        ).get("status", "unknown")
        checks.append(Check("HEALTH", "PASS" if response.status_code == 200 else "FAIL",
                            f"status_code={response.status_code} status={public_status}"))
    except Exception:
        checks.append(Check("HEALTH", "FAIL", "readiness endpoint unavailable"))
    checks.append(Check("SECRETS_REDACTED", "PASS", "sensitive values omitted"))
    return checks


def preflight_succeeded(checks: list[Check]) -> bool:
    return all(check.passed for check in checks if check.critical)
