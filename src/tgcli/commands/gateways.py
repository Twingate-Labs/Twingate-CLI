"""Gateway commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated
from tgcli.output.transformers import gateways as t
from tgcli.queries import gateways as q

app = typer.Typer(help="Manage Twingate Gateways.")


@app.command("list")
def gateway_list() -> None:
    """List all Gateways."""
    run_paginated(get_client(), q.LIST_GATEWAYS, "gateways", t.get_list_as_csv)
