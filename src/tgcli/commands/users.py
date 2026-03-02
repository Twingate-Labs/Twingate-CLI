"""User management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_paginated, run_query
from tgcli.output.transformers import users as t
from tgcli.queries import users as q
from tgcli.validators.generic import parse_bool_string
from tgcli.validators.user import validate_user_role, validate_user_state

app = typer.Typer(help="Manage Twingate users.")


@app.command("list")
def user_list() -> None:
    """List all users."""
    run_paginated(get_client(), q.LIST_USERS, "users", t.get_list_as_csv)


@app.command("show")
def user_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
) -> None:
    """Show details for a specific user."""
    run_query(get_client(), q.SHOW_USER, {"itemID": itemid}, t.get_show_as_csv)


@app.command("create")
def user_create(
    email: str = typer.Option(..., "-e", "--email", help="User email address."),
    firstname: str = typer.Option("", "-f", "--firstname", help="First name."),
    lastname: str = typer.Option(..., "-l", "--lastname", help="Last name."),
    role: str = typer.Option(..., "-r", "--role", help="Role: ADMIN, DEVOPS, SUPPORT, or MEMBER."),
    sendinvite: str = typer.Option("True", "-s", "--sendinvite", help="Send email invitation: true or false."),
) -> None:
    """Create a new user."""
    role_val = validate_user_role(role)
    invite_bool = parse_bool_string(sendinvite)
    run_query(
        get_client(),
        q.CREATE_USER,
        {
            "email": email,
            "firstname": firstname,
            "lastname": lastname,
            "userRole": role_val,
            "shouldsendinvite": invite_bool,
        },
        t.get_create_as_csv,
    )


@app.command("delete")
def user_delete(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
) -> None:
    """Delete a user."""
    run_query(get_client(), q.DELETE_USER, {"itemid": itemid}, t.get_delete_as_csv)


@app.command("role")
def user_role(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
    role: str = typer.Option(..., "-r", "--role", help="New role: ADMIN, DEVOPS, SUPPORT, or MEMBER."),
) -> None:
    """Update a user's role."""
    role_val = validate_user_role(role)
    run_query(
        get_client(),
        q.UPDATE_USER_ROLE,
        {"itemid": itemid, "userRole": role_val},
        t.get_update_role_as_csv,
    )


@app.command("state")
def user_state(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
    state_val: str = typer.Option(..., "-s", "--state", help="New state: ACTIVE or DISABLED."),
) -> None:
    """Update a user's state (active/disabled)."""
    validated_state = validate_user_state(state_val)
    run_query(
        get_client(),
        q.UPDATE_USER_STATE,
        {"userID": itemid, "state": validated_state},
        t.get_update_state_as_csv,
    )


@app.command("resetmfa")
def user_reset_mfa(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
) -> None:
    """Reset MFA for a user."""
    run_query(get_client(), q.RESET_USER_MFA, {"itemid": itemid}, t.get_reset_mfa_as_csv)
