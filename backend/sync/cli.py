"""Flask CLI commands for event synchronization."""

import click
from flask import current_app

from backend.extensions import db
from backend.models import SyncState
from backend.sync.engine import EventSynchronizer


def register_sync_commands(app):
    @app.cli.command("sync-events")
    @click.option("--once", is_flag=True, required=True, help="Run one synchronization cycle.")
    def sync_events(once):
        synchronizer = EventSynchronizer(current_app)
        synchronizer.validate_startup()
        count = synchronizer.run_once()
        click.echo(f"synced_events={count}")

    @app.cli.command("sync-status")
    def sync_status():
        cursor = SyncState.query.filter_by(
            chain_id=current_app.config["CHAIN_ID"],
            contract_address="0x0000000000000000000000000000000000000000",
        ).first()
        if cursor is None:
            click.echo("status=not_started")
            return
        click.echo(
            f"status={cursor.status} last_synced_block={cursor.last_synced_block} "
            f"latest_chain_block={cursor.latest_chain_block}"
        )
