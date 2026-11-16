"""Operator-only CLI commands. These use sfc_ops, never sfc_app."""

from __future__ import annotations

import getpass
import json
import secrets
from datetime import datetime, timedelta
from typing import Any

import click
from flask import Flask
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .extensions import build_engine
from .models import AppUser, Donation, UserCredential
from .security.tokens import new_opaque_token, token_hash
from .services.accounts import provision_user


def _ops_session(app: Flask) -> Any:
    settings: Settings = app.extensions["sfc_settings"]
    engine = build_engine(settings.ops_database_url, settings.ops_database_password)
    if engine is None:
        raise click.ClickException("SFC_OPS_DATABASE_URL is not configured.")
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def register_cli(app: Flask) -> None:
    @app.cli.group("operator")
    def operator() -> None:
        """Operator provisioning commands (sfc_ops credentials)."""

    @operator.command("create-user")
    @click.option("--email", required=True)
    @click.option("--full-name", required=True)
    @click.option("--phone", required=True)
    @click.option(
        "--role",
        required=True,
        type=click.Choice(["DONOR", "NGO_MANAGER", "DRIVER", "SAFETY_INSPECTOR"]),
    )
    @click.option("--branch-id", type=int, default=None)
    @click.option("--supervisor-user-id", type=int, default=None)
    def create_user(
        email: str,
        full_name: str,
        phone: str,
        role: str,
        branch_id: int | None,
        supervisor_user_id: int | None,
    ) -> None:
        factory = _ops_session(app)
        with factory() as db:
            user, token = provision_user(
                db,
                full_name=full_name,
                email=email,
                phone=phone,
                role=role,
                branch_id=branch_id,
                supervisor_user_id=supervisor_user_id,
            )
            click.echo(
                json.dumps(
                    {
                        "user_id": user.user_id,
                        "email": user.email,
                        "role": user.user_role,
                        "activation_token": token,
                        "delivery": "shown_once",
                    }
                )
            )

    @operator.command("issue-activation")
    @click.option("--email", required=True)
    def issue_activation(email: str) -> None:
        factory = _ops_session(app)
        with factory() as db:
            row = db.execute(
                select(AppUser, UserCredential)
                .join(UserCredential, UserCredential.user_id == AppUser.user_id)
                .where(func.lower(AppUser.email) == email.casefold())
                .with_for_update()
            ).first()
            if row is None:
                raise click.ClickException("No such user.")
            user, credential = row
            token = new_opaque_token()
            credential.reset_token_hash = token_hash(token)
            credential.reset_expires_at = datetime.now() + timedelta(hours=24)
            credential.must_change_password = True
            db.commit()
            click.echo(
                json.dumps(
                    {
                        "user_id": user.user_id,
                        "activation_token": token,
                        "delivery": "shown_once",
                    }
                )
            )

    @operator.command("issue-reset")
    @click.option("--email", required=True)
    def issue_reset(email: str) -> None:
        factory = _ops_session(app)
        with factory() as db:
            row = db.execute(
                select(AppUser, UserCredential)
                .join(UserCredential, UserCredential.user_id == AppUser.user_id)
                .where(func.lower(AppUser.email) == email.casefold())
                .with_for_update()
            ).first()
            if row is None:
                raise click.ClickException("No such user.")
            user, credential = row
            token = new_opaque_token()
            credential.reset_token_hash = token_hash(token)
            credential.reset_expires_at = datetime.now() + timedelta(hours=1)
            db.commit()
            click.echo(
                json.dumps(
                    {"user_id": user.user_id, "reset_token": token, "delivery": "shown_once"}
                )
            )

    @operator.command("set-donor-branch")
    @click.option("--email", required=True)
    @click.option("--branch-id", required=True, type=int)
    def set_donor_branch(email: str, branch_id: int) -> None:
        factory = _ops_session(app)
        with factory() as db:
            donor = db.scalar(
                select(AppUser).where(
                    func.lower(AppUser.email) == email.casefold(),
                    AppUser.user_role == "DONOR",
                )
            )
            if donor is None:
                raise click.ClickException("No such donor.")
            donor.primary_branch_id = branch_id
            db.commit()
            click.echo(json.dumps({"user_id": donor.user_id, "branch_id": branch_id}))

    @app.cli.group("queue")
    def queue() -> None:
        """Read-only operator queue views."""

    @queue.command("unrouted")
    @click.option("--orphans", is_flag=True, help="Only donations with no branch anchor.")
    def queue_unrouted(orphans: bool) -> None:
        factory = _ops_session(app)
        invocation = secrets.token_hex(8)
        with factory() as db:
            stmt = (
                select(Donation, AppUser)
                .join(AppUser, AppUser.user_id == Donation.donor_user_id)
                .where(Donation.pickup_route_id.is_(None))
                .order_by(Donation.pickup_datetime.asc())
            )
            if orphans:
                stmt = stmt.where(AppUser.primary_branch_id.is_(None))
            rows = db.execute(stmt).all()
            payload = [
                {
                    "donation_id": donation.donation_id,
                    "donor_user_id": donor.user_id,
                    "donor_name": donor.full_name,
                    "pickup_datetime": donation.pickup_datetime.isoformat(),
                    "donation_status": donation.donation_status,
                }
                for donation, donor in rows
            ]
            click.echo(json.dumps(payload, default=str))
            app.logger.info(
                "Operator unrouted queue",
                extra={
                    "event": "operator_unrouted_queue",
                    "operator": getpass.getuser(),
                    "record_count": len(payload),
                    "invocation_id": invocation,
                },
            )
