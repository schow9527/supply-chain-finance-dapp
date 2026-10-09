import pytest
from sqlalchemy import text
from web3 import Web3

from backend.app import create_app
from backend.extensions import db
from backend.preflight import Check, _chain_checks, _migration_check, collect_preflight
from backend.storage import RenderDiskStorage


def test_preflight_all_pass_returns_zero(app, monkeypatch):
    checks = [Check(name, "PASS") for name in (
        "CONFIG", "DEBUG", "DATABASE", "MIGRATIONS", "CHAIN_ID",
        "CONTRACTS", "CONTRACT_LINKS", "STORAGE", "SECRETS_REDACTED",
    )]
    checks.append(Check("EVENT_SYNC", "NOT_STARTED", critical=False))
    monkeypatch.setattr("backend.sync.cli.collect_preflight", lambda _app, role=None: checks)
    result = app.test_cli_runner().invoke(args=["production-preflight"])
    assert result.exit_code == 0
    assert "SECRETS_REDACTED=PASS" in result.output


@pytest.mark.parametrize("failed", [
    "DATABASE", "MIGRATIONS", "CHAIN_ID", "CONTRACTS", "CONTRACT_LINKS", "STORAGE",
])
def test_preflight_critical_failure_returns_nonzero(app, monkeypatch, failed):
    checks = [Check(failed, "FAIL", "safe failure")]
    monkeypatch.setattr("backend.sync.cli.collect_preflight", lambda _app, role=None: checks)
    result = app.test_cli_runner().invoke(args=["production-preflight"])
    assert result.exit_code != 0
    assert f"{failed}=FAIL" in result.output


def test_real_preflight_redacts_configured_values(app):
    secret = "must-not-appear"
    app.config["WEB3_PROVIDER_URI"] = ""
    app.config["S3_SECRET_ACCESS_KEY"] = secret
    result = app.test_cli_runner().invoke(args=["production-preflight", "--role", "worker"])
    assert result.exit_code != 0
    assert secret not in result.output
    assert "REAL_SEPOLIA_RPC_NOT_CONFIGURED" in result.output


class FakeCall:
    def __init__(self, value):
        self.value = value

    def call(self):
        return self.value


class FakeFunctions:
    def __init__(self, contract_name, values):
        self.contract_name = contract_name
        self.values = values

    def __getattr__(self, function):
        return lambda *_args: FakeCall(self.values.get((self.contract_name, function), 1))


class FakeChainEth:
    def __init__(self, app):
        self.chain_id = 11155111
        self.block_number = 11868898
        self.missing_code = None
        self.code_addresses = []
        self.names = {value.lower(): name for name, value in app.config["CONTRACT_ADDRESSES"].items()}
        addresses = app.config["CONTRACT_ADDRESSES"]
        self.values = {
            ("InvoiceRegistry", "receivableToken"): addresses["ReceivableToken"],
            ("FinancingPool", "receivableToken"): addresses["ReceivableToken"],
            ("FinancingPool", "stablecoin"): addresses["MockStablecoin"],
            ("ReceivableToken", "invoiceRegistry"): addresses["InvoiceRegistry"],
            ("ReceivableToken", "financingPool"): addresses["FinancingPool"],
        }

    def get_code(self, address):
        self.code_addresses.append(address)
        missing = self.missing_code and address.lower() == self.missing_code.lower()
        return b"" if missing else b"\x60\x00"

    def contract(self, address, abi):
        name = self.names[address.lower()]
        return type("FakeContract", (), {"functions": FakeFunctions(name, self.values)})()


class FakeChain:
    def __init__(self, app):
        self.eth = FakeChainEth(app)


def test_chain_preflight_validates_views_bytecode_and_links(app):
    app.config["CONTRACT_ADDRESSES"] = {
        name: address.lower()
        for name, address in app.config["CONTRACT_ADDRESSES"].items()
    }
    fake = FakeChain(app)
    app.config.update(WEB3_PROVIDER_URI="test://readonly", PREFLIGHT_WEB3=fake)
    checks = {check.name: check for check in _chain_checks(app)}
    assert all(check.status == "PASS" for check in checks.values())
    assert all(Web3.is_checksum_address(address) for address in fake.eth.code_addresses)


def test_contract_address_failure_does_not_reclassify_chain_id(app):
    secret = "rpc-secret-must-not-leak"
    fake = FakeChain(app)
    app.config.update(WEB3_PROVIDER_URI=f"test://{secret}", PREFLIGHT_WEB3=fake)
    app.config["CONTRACT_ADDRESSES"]["InvoiceRegistry"] = "0x1234"

    checks = {check.name: check for check in _chain_checks(app)}

    assert checks["CHAIN_ID"].status == "PASS"
    assert checks["CONTRACTS"].status == "FAIL"
    assert "InvoiceRegistry" in checks["CONTRACTS"].detail
    assert "INVALID_CONTRACT_ADDRESS" in checks["CONTRACTS"].detail
    assert secret not in " ".join(check.detail for check in checks.values())


def test_chain_preflight_rejects_wrong_chain_missing_code_and_bad_link(app):
    fake = FakeChain(app)
    app.config.update(WEB3_PROVIDER_URI="test://readonly", PREFLIGHT_WEB3=fake)
    fake.eth.chain_id = 1
    assert _chain_checks(app)[0].status == "FAIL"
    fake.eth.chain_id = 11155111
    fake.eth.missing_code = app.config["CONTRACT_ADDRESSES"]["RoleManager"]
    assert {item.name: item.status for item in _chain_checks(app)}["CONTRACTS"] == "FAIL"
    fake.eth.missing_code = None
    fake.eth.values[("InvoiceRegistry", "receivableToken")] = "0x" + "f" * 40
    assert {item.name: item.status for item in _chain_checks(app)}["CONTRACT_LINKS"] == "FAIL"


def test_migration_preflight_detects_head_and_drift(tmp_path):
    uri = f"sqlite+pysqlite:///{(tmp_path / 'preflight.sqlite').as_posix()}"
    app = create_app({"TESTING": True, "ENV_NAME": "testing",
                      "SQLALCHEMY_DATABASE_URI": uri})
    assert app.test_cli_runner().invoke(args=["db", "upgrade"]).exit_code == 0
    with app.app_context():
        assert _migration_check().status == "PASS"
        db.session.execute(text("CREATE TABLE unexpected_drift (id INTEGER PRIMARY KEY)"))
        db.session.commit()
        assert _migration_check().status == "FAIL"
        db.engine.dispose()


def test_collect_preflight_reports_storage_failure_without_secrets(app):
    class UnhealthyStorage:
        def health_check(self):
            return False

    app.config["STORAGE_SERVICE"] = UnhealthyStorage()
    checks = {check.name: check for check in collect_preflight(app)}
    assert checks["STORAGE"].status == "FAIL"
    assert checks["SECRETS_REDACTED"].status == "PASS"


def test_role_preflight_separates_web_storage_from_worker_chain(app):
    app.config["WEB3_PROVIDER_URI"] = ""
    app.config.update(STORAGE_BACKEND="render_disk",
                      RENDER_DISK_MOUNT_PATH="missing",
                      UPLOAD_FOLDER="missing")
    web = {check.name for check in collect_preflight(app, role="web")}
    worker = {check.name for check in collect_preflight(app, role="worker")}
    assert "STORAGE" in web and "CHAIN_ID" not in web and "SYNC_STATE" not in web
    assert "STORAGE" not in worker and "CHAIN_ID" in worker and "SYNC_STATE" in worker


def test_web_preflight_checks_render_disk_without_exposing_mount(app, tmp_path):
    app.config.update(
        STORAGE_BACKEND="render_disk",
        STORAGE_SERVICE=RenderDiskStorage(tmp_path, tmp_path, min_free_bytes=1),
    )
    checks = {check.name: check for check in collect_preflight(app, role="web")}
    assert checks["STORAGE"].status == "PASS"
    assert "free_space=" in checks["STORAGE"].detail
    assert str(tmp_path) not in checks["STORAGE"].detail


def test_post_deploy_verify_is_read_only_and_redacted(app, monkeypatch):
    checks = [Check("DATABASE", "PASS"), Check("MIGRATIONS", "PASS"),
              Check("STORAGE", "PASS"), Check("CHAIN_ID", "PASS"),
              Check("CONTRACTS", "PASS"), Check("CONTRACT_LINKS", "PASS"),
              Check("SYNC_STATE", "NOT_STARTED", critical=False),
              Check("SYNC_LAG", "WARN", critical=False),
              Check("SECRETS_REDACTED", "PASS")]
    monkeypatch.setattr("backend.sync.cli.collect_post_deploy", lambda _app: checks)
    result = app.test_cli_runner().invoke(args=["post-deploy-verify"])
    assert result.exit_code == 0
    assert "SYNC_LAG=WARN" in result.output
    assert "SECRETS_REDACTED=PASS" in result.output
