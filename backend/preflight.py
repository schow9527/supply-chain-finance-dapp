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

from backend.config import BASE_DIR, CONTRACT_NAMES, DEPLOYMENT_FILE, ZERO_ADDRESS
from backend.extensions import db
from backend.models import SyncState
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
    try:
        from web3 import Web3
        web3 = app.config.get("PREFLIGHT_WEB3") or Web3(
            Web3.HTTPProvider(uri, request_kwargs={"timeout": 10})
        )
        chain_id = int(web3.eth.chain_id)
        latest = int(web3.eth.block_number)
        if chain_id != 11155111:
            return [Check("CHAIN_ID", "FAIL", f"chain_id={chain_id}"),
                    Check("CONTRACTS", "FAIL", "wrong chain"),
                    Check("CONTRACT_LINKS", "FAIL", "wrong chain")]
        deployment = json.loads(DEPLOYMENT_FILE.read_text(encoding="utf-8"))
        if latest < int(deployment["startBlock"]):
            return [Check("CHAIN_ID", "FAIL", "latest block precedes start block"),
                    Check("CONTRACTS", "FAIL", "invalid block range"),
                    Check("CONTRACT_LINKS", "FAIL", "invalid block range")]
        contracts = {}
        for name in CONTRACT_NAMES:
            address = app.config["CONTRACT_ADDRESSES"][name]
            code = web3.eth.get_code(address)
            if not code or code.hex() in {"", "0x", "00", "0x00"}:
                return [Check("CHAIN_ID", "PASS", f"chain_id={chain_id} latest={latest}"),
                        Check("CONTRACTS", "FAIL", f"bytecode missing for {name}"),
                        Check("CONTRACT_LINKS", "FAIL", "contract check failed")]
            abi = json.loads((ABI_DIR / f"{name}.json").read_text(encoding="utf-8"))
            contracts[name] = web3.eth.contract(address=address, abi=abi)
        admin = deployment["admin"]
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
        links = [
            ("InvoiceRegistry", "receivableToken", "ReceivableToken"),
            ("FinancingPool", "receivableToken", "ReceivableToken"),
            ("FinancingPool", "stablecoin", "MockStablecoin"),
            ("ReceivableToken", "invoiceRegistry", "InvoiceRegistry"),
            ("ReceivableToken", "financingPool", "FinancingPool"),
        ]
        for owner, function, target in links:
            actual = getattr(contracts[owner].functions, function)().call()
            if str(actual).lower() != app.config["CONTRACT_ADDRESSES"][target].lower():
                return [Check("CHAIN_ID", "PASS", f"chain_id={chain_id} latest={latest}"),
                        Check("CONTRACTS", "PASS", "five bytecodes and views"),
                        Check("CONTRACT_LINKS", "FAIL", f"{owner}.{function} mismatch")]
        return [Check("CHAIN_ID", "PASS", f"chain_id={chain_id} latest={latest}"),
                Check("CONTRACTS", "PASS", "five bytecodes and views"),
                Check("CONTRACT_LINKS", "PASS", "five references")]
    except Exception as exc:
        return [Check("CHAIN_ID", "FAIL", f"read-only RPC check failed ({type(exc).__name__})"),
                Check("CONTRACTS", "FAIL", "RPC validation incomplete"),
                Check("CONTRACT_LINKS", "FAIL", "RPC validation incomplete")]


def collect_preflight(app) -> list[Check]:
    checks = [
        Check("CONFIG", "PASS" if app.config.get("ENV_NAME") == "production" else "FAIL",
              f"mode={app.config.get('ENV_NAME', 'unknown')}"),
        Check("DEBUG", "PASS" if not app.config.get("DEBUG") and not app.config.get("TESTING") else "FAIL",
              "disabled" if not app.config.get("DEBUG") else "enabled"),
    ]
    checks.extend(_database_checks(app))
    checks.extend(_chain_checks(app))
    try:
        storage_ok = app.config.get("STORAGE_BACKEND") == "s3" and get_storage().health_check()
    except Exception:
        storage_ok = False
    checks.append(Check("STORAGE", "PASS" if storage_ok else "FAIL",
                        f"backend={app.config.get('STORAGE_BACKEND', 'unknown')}"))
    try:
        cursor = SyncState.query.filter_by(
            chain_id=app.config.get("CHAIN_ID"), contract_address=ZERO_ADDRESS
        ).first()
        detail = (f"last_synced_block={cursor.last_synced_block} status={cursor.status}"
                  if cursor else "no cursor")
        checks.append(Check("EVENT_SYNC", "PASS" if cursor else "NOT_STARTED",
                            detail, critical=False))
    except Exception:
        checks.append(Check("EVENT_SYNC", "NOT_STARTED", "state unavailable", critical=False))
    checks.append(Check("SECRETS_REDACTED", "PASS", "sensitive values omitted"))
    return checks


def preflight_succeeded(checks: list[Check]) -> bool:
    return all(check.passed for check in checks if check.critical)
