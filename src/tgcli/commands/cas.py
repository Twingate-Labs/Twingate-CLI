"""Certificate authority management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import cas as t
from tgcli.queries import cas as q

app = typer.Typer(help="Manage Certificate Authorities.")


@app.command("list")
def ca_list() -> None:
    """List all Certificate Authorities."""
    run_paginated(get_client(), q.LIST_CAS, "certificateAuthorities", t.get_list_as_csv)


@app.command("show")
def ca_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Certificate Authority ID."),
) -> None:
    """Show details for a Certificate Authority."""
    run_query(get_client(), q.SHOW_CA, {"itemID": itemid}, t.get_show_as_csv)


@app.command("createSSH")
def ca_create_ssh(
    name: str = typer.Option(..., "-n", "--name", help="SSH CA name."),
    publickey: str = typer.Option(..., "-k", "--publickey", help="SSH public key."),
) -> None:
    """Create an SSH Certificate Authority."""
    run_query(get_client(), q.CREATE_SSH_CA, {"name": name, "publicKey": publickey}, t.get_create_ssh_as_csv)


@app.command("deleteSSH")
def ca_delete_ssh(
    itemid: str = typer.Option(..., "-i", "--itemid", help="SSH CA ID."),
) -> None:
    """Delete an SSH Certificate Authority."""
    run_query(get_client(), q.DELETE_SSH_CA, {"id": itemid}, t.get_delete_ssh_as_csv)


@app.command("createX509")
def ca_create_x509(
    name: str = typer.Option(..., "-n", "--name", help="X509 CA name."),
    certificate: str = typer.Option(..., "-c", "--certificate", help="X509 certificate PEM."),
) -> None:
    """Create an X509 Certificate Authority."""
    run_query(get_client(), q.CREATE_X509_CA, {"name": name, "certificate": certificate}, t.get_create_x509_as_csv)


@app.command("deleteX509")
def ca_delete_x509(
    itemid: str = typer.Option(..., "-i", "--itemid", help="X509 CA ID."),
) -> None:
    """Delete an X509 Certificate Authority."""
    run_query(get_client(), q.DELETE_X509_CA, {"id": itemid}, t.get_delete_x509_as_csv)
