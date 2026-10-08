"""DNS Filtering profile management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import execute_query, get_client, run_query
from tgcli.output.transformers import dns_profiles as t
from tgcli.queries import dns_profiles as q

app = typer.Typer(help="Manage Twingate DNS Filtering profiles.")


@app.command("list")
def dns_profile_list() -> None:
    """List all DNS Filtering profiles."""
    run_query(get_client(), q.LIST_DNS_PROFILES, None, t.get_list_as_csv)


@app.command("show")
def dns_profile_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="DNS Filtering Profile ID."),
) -> None:
    """Show details for a specific DNS Filtering profile, including assigned groups."""
    run_query(get_client(), q.SHOW_DNS_PROFILE, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def dns_profile_create(
    name: str = typer.Option(..., "-n", "--name", help="DNS Filtering profile name."),
) -> None:
    """Create a DNS Filtering profile (name only; the API applies its default settings)."""
    run_query(get_client(), q.CREATE_DNS_PROFILE, {"name": name}, t.get_create_as_csv)


@app.command("delete")
def dns_profile_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="DNS Filtering Profile ID."),
) -> None:
    """Delete a DNS Filtering profile. Groups assigned to it lose its filtering. Cannot be undone."""
    client = get_client()
    if execute_query(client, q.FIND_DNS_PROFILE, {"itemID": itemid})["data"]["dnsFilteringProfile"] is None:
        typer.echo(f"Error: DNS Filtering profile {itemid} not found.", err=True)
        raise typer.Exit(1)
    run_query(client, q.DELETE_DNS_PROFILE, {"id": itemid}, t.get_delete_as_csv)
