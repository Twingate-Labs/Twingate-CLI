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


@app.command("create")
def dnssec_create(
    name: str = typer.Option(..., "-n", "--name", help="DNS filtering profile name."),
    priority: float = typer.Option(None, "--priority", help="Profile priority."),
) -> None:
    """Create a new DNS filtering profile."""
    variables: dict = {"name": name}
    if priority is not None:
        variables["priority"] = priority
    run_query(get_client(), q.CREATE_DNS_PROFILE, variables, t.get_create_as_csv)


@app.command("delete")
def dnssec_delete(
    profileid: str = typer.Option("", "-i", "--profileid", help="DNS profile ID (auto-detected if omitted)."),
) -> None:
    """Delete a DNS filtering profile."""
    client = get_client()
    pid = profileid or _get_profile_id(client)
    run_query(client, q.DELETE_DNS_PROFILE, {"id": pid}, t.get_delete_as_csv)


@app.command("update")
def dnssec_update(
    profileid: str = typer.Option("", "-i", "--profileid", help="DNS profile ID (auto-detected if omitted)."),
    name: str = typer.Option("", "-n", "--name", help="New profile name."),
    priority: float = typer.Option(None, "--priority", help="Profile priority."),
    fallback: str = typer.Option("", "--fallback", help="Fallback method: AUTO or STRICT."),
    groups: str = typer.Option("", "-g", "--groups", help="Comma-separated Group IDs to assign."),
    allowed: str = typer.Option("", "--allowed", help="Comma-separated allowed domains."),
    denied: str = typer.Option("", "--denied", help="Comma-separated denied domains."),
) -> None:
    """Update a DNS filtering profile (full update including categories and groups)."""
    from tgcli.commands._common import split_ids
    client = get_client()
    pid = profileid or _get_profile_id(client)
    variables: dict = {"id": pid}
    if name:
        variables["name"] = name
    if priority is not None:
        variables["priority"] = priority
    if fallback:
        variables["fallbackMethod"] = fallback.upper()
    if groups:
        variables["groups"] = split_ids(groups)
    if allowed:
        variables["allowedDomains"] = [d.strip() for d in allowed.split(",") if d.strip()]
    if denied:
        variables["deniedDomains"] = [d.strip() for d in denied.split(",") if d.strip()]
    run_query(client, q.UPDATE_DNS_PROFILE_FULL, variables, t.get_update_allow_as_csv)
