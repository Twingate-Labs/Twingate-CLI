"""DNS security management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_query
from tgcli.output.transformers import dnssec as t
from tgcli.queries import dnssec as q

app = typer.Typer(help="Manage Twingate DNS security (filtering) settings.")


@app.command("show")
def dnssec_show() -> None:
    """Show the current DNS filtering profile (allow/deny lists)."""
    run_query(get_client(), q.SHOW_DNS_PROFILE, None, t.get_show_as_csv)


@app.command("setAllowList")
def dnssec_set_allow_list(
    domains: str = typer.Option(..., "-d", "--domains", help="Comma-separated list of allowed domains."),
) -> None:
    """Set the DNS allow list (replaces existing)."""
    domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    run_query(get_client(), q.SET_ALLOWED_DOMAINS, {"domains": domain_list}, t.get_update_allow_as_csv)


@app.command("setDenyList")
def dnssec_set_deny_list(
    domains: str = typer.Option(..., "-d", "--domains", help="Comma-separated list of denied domains."),
) -> None:
    """Set the DNS deny list (replaces existing)."""
    domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    run_query(get_client(), q.SET_DENIED_DOMAINS, {"domains": domain_list}, t.get_update_deny_as_csv)
