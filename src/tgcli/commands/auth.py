"""Authentication commands: login, logout, list."""

from __future__ import annotations

import typer

from tgcli.client.exceptions import TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import state

app = typer.Typer(help="Manage authentication sessions.")


def _session_name(local: str) -> str:
    """Resolve session name: local arg > global state > random."""
    return local or state.session or SessionManager.random_session_name()


@app.command("login")
def login(
    apikey: str = typer.Option(..., "-a", "--apikey", help="Twingate API key."),
    tenant: str = typer.Option(..., "-t", "--tenant", help="Twingate network tenant (e.g. 'mycompany')."),
    session: str = typer.Option("", "-s", "--session", help="Session name (auto-generated if omitted)."),
    staging: bool = typer.Option(False, "--staging", help="Use staging environment.", hidden=True),
) -> None:
    """Authenticate with the Twingate API and store credentials."""
    session_name = _session_name(session)
    SessionManager.store(session_name, tenant, apikey, staging=staging)
    typer.echo(f"✓ Session created: [bold]{session_name}[/bold]" if False else f"Session created: {session_name}")


@app.command("logout")
def logout(
    session: str = typer.Option("", "-s", "--session", help="Session name to remove."),
) -> None:
    """Remove a stored session's credentials."""
    session_name = session or state.session
    if not session_name:
        typer.echo("Error: No session name. Use -s or the global --session flag.", err=True)
        raise typer.Exit(1)
    SessionManager.delete(session_name)
    typer.echo(f"Session deleted: {session_name}")


@app.command("list")
def list_sessions() -> None:
    """List all stored session names."""
    sessions = SessionManager.list_sessions()
    if sessions:
        for s in sessions:
            typer.echo(s)
    else:
        typer.echo("No sessions found.")
