from sqlalchemy import create_engine, inspect

from backend.app import create_app
from backend.extensions import db


def test_migration_upgrade_downgrade_upgrade(tmp_path):
    database = tmp_path / "migration.sqlite"
    uri = f"sqlite+pysqlite:///{database.as_posix()}"
    app = create_app({
        "TESTING": True,
        "ENV_NAME": "testing",
        "SQLALCHEMY_DATABASE_URI": uri,
        "WEB3_PROVIDER_URI": "test://disabled",
        "RPC_HEALTHCHECK_ENABLED": False,
    })
    runner = app.test_cli_runner()
    first = runner.invoke(args=["db", "upgrade"])
    assert first.exit_code == 0, first.output
    first_check = runner.invoke(args=["db", "check"])
    assert first_check.exit_code == 0, first_check.output
    engine = create_engine(uri)
    table_names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert table_names >= {
        "enterprises", "invoices", "holdings", "financing_requests", "quotes",
        "chain_events", "sync_state", "auth_nonces",
    }
    down = runner.invoke(args=["db", "downgrade", "base"])
    assert down.exit_code == 0, down.output
    second = runner.invoke(args=["db", "upgrade"])
    assert second.exit_code == 0, second.output
    second_check = runner.invoke(args=["db", "check"])
    assert second_check.exit_code == 0, second_check.output
    with app.app_context():
        db.engine.dispose()
