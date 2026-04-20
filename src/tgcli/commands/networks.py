"""Remote network management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import networks as t
from tgcli.queries import networks as q
from tgcli.validators.generic import parse_bool_string
from tgcli.validators.network import validate_rn_location

app = typer.Typer(help="Manage Twingate Remote Networks.")


@app.command("list")
def network_list() -> None:
    """List all Remote Networks."""
    run_paginated(get_client(), q.LIST_NETWORKS, "remoteNetworks", t.get_list_as_csv)


@app.command("show")
def network_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Remote Network ID."),
) -> None:
    """Show details for a specific Remote Network."""
    run_query(get_client(), q.SHOW_NETWORK, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def network_create(
    name: str = typer.Option(..., "-n", "--name", help="Remote Network name."),
    active: str = typer.Option(..., "-a", "--active", help="Active state: true or false."),
    location: str = typer.Option("OTHER", "-l", "--location", help="Location: AWS, AZURE, GOOGLE_CLOUD, ON_PREMISE, or OTHER."),
) -> None:
    """Create a new Remote Network."""
    active_bool = parse_bool_string(active)
    location_val = validate_rn_location(location)
    run_query(
        get_client(),
        q.CREATE_NETWORK,
        {"name": name, "location": location_val, "isactive": active_bool},
        t.get_create_as_csv,
    )


@app.command("delete")
def network_delete(
    id: str = typer.Option(..., "-i", "--id", help="Remote Network ID."),
) -> None:
    """Delete a Remote Network."""
    run_query(get_client(), q.DELETE_NETWORK, {"id": id}, t.get_delete_as_csv)


@app.command("updateState")
def network_update_state(
    id: str = typer.Option(..., "-i", "--id", help="Remote Network ID."),
    active: str = typer.Option(..., "-a", "--active", help="Active: true or false."),
) -> None:
    """Activate or deactivate a Remote Network."""
    active_bool = parse_bool_string(active)
    run_query(
        get_client(),
        q.UPDATE_NETWORK_STATE,
        {"rnID": id, "state": active_bool},
        t.get_update_as_csv,
    )


@app.command("updateName")
def network_update_name(
    id: str = typer.Option(..., "-i", "--id", help="Remote Network ID."),
    name: str = typer.Option(..., "-n", "--name", help="New Remote Network name."),
) -> None:
    """Rename a Remote Network."""
    run_query(get_client(), q.UPDATE_NETWORK_NAME, {"rnID": id, "name": name}, t.get_update_as_csv)


@app.command("updateLocation")
def network_update_location(
    id: str = typer.Option(..., "-i", "--id", help="Remote Network ID."),
    location: str = typer.Option(..., "-l", "--location", help="Location: AWS, AZURE, GOOGLE_CLOUD, ON_PREMISE, or OTHER."),
) -> None:
    """Update a Remote Network's location."""
    location_val = validate_rn_location(location)
    run_query(
        get_client(),
        q.UPDATE_NETWORK_LOCATION,
        {"rnID": id, "location": location_val},
        t.get_update_as_csv,
    )
