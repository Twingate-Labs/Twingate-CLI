"""Service account key management commands."""

from __future__ import annotations

import json

import pandas as pd
import typer

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client, run_query
from tgcli.main import state
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


@app.command("rotate")
def key_rotate(
    itemid: str = typer.Option(..., "-i", "--itemid", help="ID of the Key to rotate."),
    expiration: int = typer.Option(1, "-e", "--expiration", help="Expiration in days for the new Key (0–365)."),
    name: str = typer.Option("", "-n", "--name", help="Name for the new Key. Defaults to '<old name> (rotated)'."),
) -> None:
    """Rotate a Service Account Key: create a new Key on the same Service Account, then revoke the old one.

    The Twingate API has no native rotate mutation, so this orchestrates
    a serviceAccountKeyCreate followed by a serviceAccountKeyRevoke. If
    creating the new Key fails, the old Key is left untouched. If the new
    Key is created but revoking the old Key fails, both Keys are left
    active and the old Key ID is reported so it can be revoked manually.
    """
    exp_val = validate_key_expiration(expiration)
    client = get_client()

    try:
        show_result = client.execute(q.SHOW_KEY, {"itemID": itemid})
    except (TwingateAuthError, TwingateAPIError) as exc:
        typer.echo(f"Error fetching Key '{itemid}': {exc}", err=True)
        raise typer.Exit(1)

    old_key = show_result["data"]["serviceAccountKey"]
    if old_key is None:
        typer.echo(f"Error: No Key found with ID '{itemid}'.", err=True)
        raise typer.Exit(1)

    service_account = old_key.get("serviceAccount") or {}
    service_account_id = service_account.get("id")
    if not service_account_id:
        typer.echo(f"Error: Could not determine the Service Account for Key '{itemid}'.", err=True)
        raise typer.Exit(1)

    new_name = name or f"{old_key['name']} (rotated)"

    typer.echo(
        f"Creating new Key '{new_name}' on Service Account "
        f"'{service_account.get('name')}' ({service_account_id})..."
    )
    try:
        create_result = client.execute(
            q.CREATE_KEY,
            {"name": new_name, "serviceAccountId": service_account_id, "expirationTime": exp_val},
        )
    except (TwingateAuthError, TwingateAPIError) as exc:
        typer.echo(f"Error creating new Key: {exc}", err=True)
        raise typer.Exit(1)

    create_data = create_result["data"]["serviceAccountKeyCreate"]
    if not create_data["ok"]:
        typer.echo(f"Error: Key creation failed: {create_data['error']}", err=True)
        raise typer.Exit(1)

    new_entity = create_data["entity"]
    typer.echo(f"Created new Key: {new_entity['id']}")

    typer.echo(f"Revoking old Key '{itemid}'...")
    try:
        revoke_result = client.execute(q.REVOKE_KEY, {"id": itemid})
    except (TwingateAuthError, TwingateAPIError) as exc:
        typer.echo(
            f"Warning: new Key {new_entity['id']} was created, but revoking the old Key "
            f"failed: {exc}. Revoke it manually with: tgcli key revoke -i {itemid}",
            err=True,
        )
        raise typer.Exit(1)

    revoke_data = revoke_result["data"]["serviceAccountKeyRevoke"]
    if not revoke_data["ok"]:
        typer.echo(
            f"Warning: new Key {new_entity['id']} was created, but revoking the old Key "
            f"failed: {revoke_data['error']}. Revoke it manually with: "
            f"tgcli key revoke -i {itemid}",
            err=True,
        )
        raise typer.Exit(1)

    result = {
        "oldKeyId": itemid,
        "oldKeyRevoked": True,
        "serviceAccountId": service_account_id,
        "serviceAccountName": service_account.get("name"),
        "newKeyId": new_entity["id"],
        "newKeyName": new_entity["name"],
        "newKeyToken": create_data["token"],
        "newKeyExpiresAt": new_entity.get("expiresAt"),
    }

    fmt = state.output_format.upper()
    if fmt == "CSV":
        typer.echo(pd.json_normalize([result]).to_csv(index=False))
    elif fmt == "DF":
        typer.echo(pd.json_normalize([result]).to_string())
    else:
        typer.echo(json.dumps(result, indent=2, default=str))
