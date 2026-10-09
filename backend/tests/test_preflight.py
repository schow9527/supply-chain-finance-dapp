import pytest
from sqlalchemy import text

from backend.app import create_app
from backend.extensions import db
from backend.preflight import Check, _chain_checks, _migration_check, collect_preflight


def test_preflight_all_pass_returns_zero(app, monkeypatch):
    checks = [Check(name, "PASS") for name in (
        "CONFIG", "DEBUG", "DATABASE", "MIGRATIONS", "CHAIN_ID",
        "CONTRACTS", "CONTRACT_LINKS", "STORAGE", "SECRETS_REDACTED",
    )]
    checks.append(Check("EVENT_SYNC", "NOT_STARTED", critical=False))
    monkeypatch.setattr("backend.sync.cli.collect_preflight", lambda _app: checks)
    result = app.test_cli_runner().invoke(args=["production-preflight"])
    assert result.exit_code == 0
    assert "SECRETS_REDACTED=PASS" in result.output


@pytest.mark.parametrize("failed", [
    "DATABASE", "MIGRATIONS", "CHAIN_ID", "CONTRACTS", "CONTRACT_LINKS", "STORAGE",
])
def test_preflight_critical_failure_returns_nonzero(app, monkeypatch, failed):
    checks = [Check(failed, "FAIL", "safe failure")]
    monkeypatch.setattr("backend.sync.cli.collect_preflight", lambda _app: checks)
    result = app.test_cli_runner().invoke(args=["production-preflight"])
    assert result.exit_code != 0
    assert f"{failed}=FAIL" in result.output


def test_real_preflight_redacts_configured_values(app):
    secret = "must-not-appear"
    app.config["WEB3_PROVIDER_URI"] = ""
    app.config["S3_SECRET_ACCESS_KEY"] = secret
    result = app.test_cli_runner().invoke(args=["production-preflight"])
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
        return b"" if address == self.missing_code else b"\x60\x00"

    def contract(self, address, abi):
        name = self.names[address.lower()]
        return type("FakeContract", (), {"functions": FakeFunctions(name, self.values)})()


class FakeChain:
    def __init__(self, app):
        self.eth = FakeChainEth(app)


def test_chain_preflight_validates_views_bytecode_and_links(app):
    fake = FakeChain(app)
    app.config.update(WEB3_PROVIDER_URI="test://readonly", PREFLIGHT_WEB3=fake)
    checks = {check.name: check for check in _chain_checks(app)}
    assert all(check.status == "PASS" for check in checks.values())


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
