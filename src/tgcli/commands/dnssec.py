"""DNS security management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_query
from tgcli.output.transformers import dnssec as t
from tgcli.queries import dnssec as q

app = typer.Typer(help="Manage Twingate DNS security (filtering) settings.")


@app.command("show")
def dnssec_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="DNS Filtering Profile ID (see 'tgcli dns-profile list')."),
) -> None:
    """Show a DNS filtering profile's allow/deny lists."""
    run_query(get_client(), q.SHOW_DNS_PROFILE, {"itemID": itemid}, t.get_show_as_csv)


@app.command("setAllowList")
def dnssec_set_allow_list(
    itemid: str = typer.Option(..., "-i", "--itemid", help="DNS Filtering Profile ID (see 'tgcli dns-profile list')."),
    domains: str = typer.Option(..., "-d", "--domains", help="Comma-separated list of allowed domains."),
) -> None:
    """Set a DNS filtering profile's allow list (replaces existing)."""
    domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    run_query(get_client(), q.SET_ALLOWED_DOMAINS, {"itemID": itemid, "domains": domain_list}, t.get_update_allow_as_csv)


@app.command("setDenyList")
def dnssec_set_deny_list(
    itemid: str = typer.Option(..., "-i", "--itemid", help="DNS Filtering Profile ID (see 'tgcli dns-profile list')."),
    domains: str = typer.Option(..., "-d", "--domains", help="Comma-separated list of denied domains."),
) -> None:
    """Set a DNS filtering profile's deny list (replaces existing)."""
    domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    run_query(get_client(), q.SET_DENIED_DOMAINS, {"itemID": itemid, "domains": domain_list}, t.get_update_deny_as_csv)
