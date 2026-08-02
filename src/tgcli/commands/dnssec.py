"""DNS security management commands."""

from __future__ import annotations

import typer

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client, run_query
from tgcli.output.transformers import dnssec as t
from tgcli.queries import dnssec as q

app = typer.Typer(help="Manage Twingate DNS security (filtering) settings.")


def _get_profile_id(client) -> str:
    """Discover the DNS filtering profile ID."""
    result = client.execute(q.LIST_DNS_PROFILES)
    profiles = result.get("data", {}).get("dnsFilteringProfiles", [])
    if not profiles:
        raise TwingateAPIError("No DNS filtering profiles found.")
    return profiles[0]["id"]


@app.command("show")
def dnssec_show() -> None:
    """Show the current DNS filtering profile (allow/deny lists)."""
    client = get_client()
    profile_id = _get_profile_id(client)
    run_query(client, q.SHOW_DNS_PROFILE, {"id": profile_id}, t.get_show_as_csv)


@app.command("setAllowList")
def dnssec_set_allow_list(
    domains: str = typer.Option(..., "-d", "--domains", help="Comma-separated list of allowed domains."),
) -> None:
    """Set the DNS allow list (replaces existing)."""
    client = get_client()
    profile_id = _get_profile_id(client)
    domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    run_query(client, q.UPDATE_DNS_PROFILE, {"id": profile_id, "allowedDomains": domain_list}, t.get_update_allow_as_csv)


@app.command("setDenyList")
def dnssec_set_deny_list(
    domains: str = typer.Option(..., "-d", "--domains", help="Comma-separated list of denied domains."),
) -> None:
    """Set the DNS deny list (replaces existing)."""
    client = get_client()
    profile_id = _get_profile_id(client)
    domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    run_query(client, q.UPDATE_DNS_PROFILE, {"id": profile_id, "deniedDomains": domain_list}, t.get_update_deny_as_csv)
