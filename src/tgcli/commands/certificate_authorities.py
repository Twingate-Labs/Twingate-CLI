"""Certificate authority commands (X.509 and SSH, used by Gateways)."""

from __future__ import annotations

import typer

from tgcli.commands._common import execute_query, get_client, run_paginated, run_query
from tgcli.output.transformers import certificate_authorities as t
from tgcli.queries import certificate_authorities as q

app = typer.Typer(help="Manage Twingate Certificate Authorities (X.509 and SSH).")


def _read_file(path: str) -> str:
    try:
        with open(path) as fh:
            content = fh.read().strip()
    except OSError as exc:
        typer.echo(f"Error: cannot read {path}: {exc.strerror}", err=True)
        raise typer.Exit(1)
    if not content:
        typer.echo(f"Error: {path} is empty.", err=True)
        raise typer.Exit(1)
    return content


@app.command("list")
def ca_list() -> None:
    """List all Certificate Authorities (both X.509 and SSH)."""
    run_paginated(get_client(), q.LIST_CAS, "certificateAuthorities", t.get_list_as_csv)


@app.command("show")
def ca_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Certificate Authority ID."),
) -> None:
    """Show details for a specific Certificate Authority."""
    run_query(get_client(), q.SHOW_CA, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def ca_create(
    ca_type: str = typer.Option(..., "-t", "--type", help="x509 or ssh."),
    name: str = typer.Option(..., "-n", "--name", help="Certificate Authority name."),
    file: str = typer.Option(
        ..., "--file", help="File with the PEM certificate (x509) or the SSH public key (ssh). Public material only."
    ),
) -> None:
    """Create a Certificate Authority from a public certificate or public key."""
    kind = ca_type.strip().lower()
    if kind not in ("x509", "ssh"):
        raise typer.BadParameter("Choose x509 or ssh.", param_hint="--type")
    content = _read_file(file)
    if kind == "x509":
        run_query(get_client(), q.CREATE_X509_CA, {"name": name, "certificate": content}, t.get_create_x509_as_csv)
    else:
        run_query(get_client(), q.CREATE_SSH_CA, {"name": name, "publicKey": content}, t.get_create_ssh_as_csv)


@app.command("delete")
def ca_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Certificate Authority ID."),
) -> None:
    """Delete a Certificate Authority (X.509 or SSH, detected automatically). Cannot be undone."""
    client = get_client()
    found = execute_query(client, q.SHOW_CA, {"itemID": itemid})["data"]["certificateAuthority"]
    if found is None:
        typer.echo(f"Error: Certificate Authority {itemid} not found.", err=True)
        raise typer.Exit(1)
    if found["__typename"] == "X509CertificateAuthority":
        run_query(client, q.DELETE_X509_CA, {"id": itemid}, t.get_delete_x509_as_csv)
    else:
        run_query(client, q.DELETE_SSH_CA, {"id": itemid}, t.get_delete_ssh_as_csv)
