"""DNS Filtering profile management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_query
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
