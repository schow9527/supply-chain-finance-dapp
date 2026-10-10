"""Flask CLI commands for event synchronization."""

import click
from flask import current_app

from backend.extensions import db
from backend.models import SyncState
from backend.sync.engine import EventSynchronizer, SyncStartupError, safe_sync_error
from backend.sync.projections import rebuild_projections as rebuild_all
from backend.preflight import collect_post_deploy, collect_preflight, preflight_succeeded


def _print_checks(checks):
    for check in checks:
        suffix = f" detail={check.detail}" if check.detail else ""
        click.echo(f"{check.name}={check.status}{suffix}")
    if not preflight_succeeded(checks):
        raise click.exceptions.Exit(1)


def register_sync_commands(app):
    @app.cli.command("production-preflight")
    @click.option("--role", type=click.Choice(["web", "worker"]), default=None)
    def production_preflight(role):
        """Run read-only deployment checks without printing secret values."""
        _print_checks(collect_preflight(current_app, role=role))

    @app.cli.command("post-deploy-verify")
    def post_deploy_verify():
        """Run combined read-only verification after an authorized deployment."""
        _print_checks(collect_post_deploy(current_app))

    @app.cli.command("sync-events")
    @click.option("--once", is_flag=True, required=True, help="Run one synchronization cycle.")
    def sync_events(once):
        try:
            synchronizer = EventSynchronizer(current_app)
            synchronizer.validate_startup()
            count = synchronizer.run_once()
            click.echo(f"synced_events={count}")
        except Exception as exc:
            db.session.rollback()
            safe = safe_sync_error(exc)
            click.echo(
                "SYNC_ERROR "
                f"code={safe['code']} http_status={safe['http_status']} "
                f"category={safe['category']} detail={safe['detail']}",
                err=True,
            )
            raise click.exceptions.Exit(1) from None

    @app.cli.command("sync-status")
    def sync_status():
        try:
            cursor = SyncState.query.filter_by(
                chain_id=current_app.config["CHAIN_ID"],
                contract_address="0x0000000000000000000000000000000000000000",
            ).first()
        except Exception:
            db.session.rollback()
            safe = safe_sync_error(SyncStartupError(
                "DATABASE_UNAVAILABLE", check_id="DATABASE",
                detail="connection_failed",
            ))
            click.echo(
                "SYNC_STATUS_ERROR "
                f"code={safe['code']} category={safe['category']} "
                f"detail={safe['detail']}",
                err=True,
            )
            raise click.exceptions.Exit(1) from None
        if cursor is None:
            click.echo("status=not_started")
            return
        click.echo(
            f"status={cursor.status} last_synced_block={cursor.last_synced_block} "
            f"latest_chain_block={cursor.latest_chain_block}"
        )

    @app.cli.command("rebuild-projections")
    @click.option("--confirm", is_flag=True, help="Confirm destructive projection rebuild.")
    def rebuild_projections(confirm):
        if not confirm:
            raise click.ClickException("Pass --confirm to rebuild chain-derived projections")
        if current_app.config.get("ENV_NAME") == "production":
            raise click.ClickException("Projection rebuild is disabled in Production")
        rebuild_all()
        click.echo("projections_rebuilt=true")
