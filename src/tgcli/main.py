"""Root Typer application — registers all sub-command groups and global state."""

from __future__ import annotations

import logging
from typing import Optional

import typer

from tgcli import VERSION

app = typer.Typer(
    name="tgcli",
    help="Twingate CLI — manage your Twingate network from the command line.",
    no_args_is_help=True,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# Global mutable state — imported by command modules to read session/format.
# ---------------------------------------------------------------------------

class GlobalState:
    session: str = ""
    output_format: str = "JSON"
    log_level: str = "ERROR"


state = GlobalState()


# ---------------------------------------------------------------------------
# Root callback — handles --version, --log, --session, --format
# ---------------------------------------------------------------------------

@app.callback()
def global_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "-v", "--version", is_eager=True, help="Show version and exit."
    ),
    log_level: str = typer.Option(
        "ERROR", "-l", "--log",
        help="Logging level: DEBUG, INFO, WARNING, ERROR.",
    ),
    session: str = typer.Option(
        "", "-s", "--session",
        help="Session name (from 'tgcli auth login').",
    ),
    output_format: str = typer.Option(
        "JSON", "-f", "--format",
        help="Output format: JSON, CSV, DF (DataFrame).",
    ),
) -> None:
    if version:
        typer.echo(f"tgcli version {VERSION}")
        raise typer.Exit()

    state.session = session
    state.output_format = output_format.upper()
    state.log_level = log_level.upper()

    numeric_level = getattr(logging, state.log_level, logging.ERROR)
    logging.basicConfig(level=numeric_level, format="%(levelname)s: %(message)s")


# ---------------------------------------------------------------------------
# Register sub-command groups (imported here to avoid circular imports)
# ---------------------------------------------------------------------------

def _register_commands() -> None:
    from tgcli.commands import (
        auth,
        connectors,
        devices,
        dnssec,
        groups,
        keys,
        mappings,
        networks,
        policies,
        posture,
        resources,
        accounts,
        users,
    )

    app.add_typer(auth.app, name="auth")
    app.add_typer(devices.app, name="device")
    app.add_typer(connectors.app, name="connector")
    app.add_typer(users.app, name="user")
    app.add_typer(groups.app, name="group")
    app.add_typer(resources.app, name="resource")
    app.add_typer(networks.app, name="network")
    app.add_typer(accounts.app, name="account")
    app.add_typer(keys.app, name="key")
    app.add_typer(policies.app, name="policy")
    app.add_typer(dnssec.app, name="dnssec")
    app.add_typer(mappings.app, name="mappings")
    app.add_typer(posture.app, name="posture")


_register_commands()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app()


if __name__ == "__main__":
    main()
