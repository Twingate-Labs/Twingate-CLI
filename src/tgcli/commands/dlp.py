"""DLP policy management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import dlp as t
from tgcli.queries import dlp as q

app = typer.Typer(help="Manage Data Loss Prevention Policies.")


@app.command("list")
def dlp_list() -> None:
    """List all DLP Policies."""
    run_paginated(get_client(), q.LIST_DLP_POLICIES, "dlpPolicies", t.get_list_as_csv)


@app.command("show")
def dlp_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="DLP Policy ID."),
) -> None:
    """Show details for a DLP Policy."""
    run_query(get_client(), q.SHOW_DLP_POLICY, {"itemID": itemid}, t.get_show_as_csv)
