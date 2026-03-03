"""Service account key management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_query
from tgcli.output.transformers import keys as t
from tgcli.queries import keys as q
from tgcli.validators.key import validate_key_expiration

app = typer.Typer(help="Manage Service Account Keys.")


@app.command("show")
def key_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Key ID."),
) -> None:
    """Show details for a Service Account Key."""
    run_query(get_client(), q.SHOW_KEY, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def key_create(
    name: str = typer.Option(..., "-n", "--name", help="Key name."),
    saccountid: str = typer.Option(..., "-i", "--saccountid", help="Service Account ID."),
    expiration: int = typer.Option(1, "-e", "--expiration", help="Expiration in days (between 0–365)."),
) -> None:
    """Create a new Service Account Key."""
    exp_val = validate_key_expiration(expiration)
    run_query(
        get_client(),
        q.CREATE_KEY,
        {"name": name, "serviceAccountId": saccountid, "expirationTime": exp_val},
        t.get_create_as_csv,
    )


@app.command("delete")
def key_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Key ID."),
) -> None:
    """Permanently delete a Service Account Key."""
    run_query(get_client(), q.DELETE_KEY, {"id": itemid}, t.get_delete_as_csv)


@app.command("revoke")
def key_revoke(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Key ID."),
) -> None:
    """Revoke a Service Account Key."""
    run_query(get_client(), q.REVOKE_KEY, {"id": itemid}, t.get_revoke_as_csv)


@app.command("rename")
def key_rename(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Key ID."),
    name: str = typer.Option(..., "-n", "--itemname", help="New Key name."),
) -> None:
    """Rename a Service Account Key."""
    run_query(get_client(), q.RENAME_KEY, {"id": itemid, "name": name}, t.get_rename_as_csv)
