"""User management commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import YES_OPTION, confirm_delete, get_client, run_paginated, run_query
from tgcli.output.transformers import users as t
from tgcli.pagination import NestedLists
from tgcli.queries import users as q
from tgcli.validators.generic import parse_bool_string
from tgcli.validators.user import VALID_ROLES, validate_user_role, validate_user_state

app = typer.Typer(help="Manage Twingate Users.")


@app.command("list")
def user_list() -> None:
    """List all Users."""
    run_paginated(
        get_client(), q.LIST_USERS, "users", t.get_list_as_csv,
        nested=NestedLists("user", q.USER_LIST_CONTINUATIONS),
    )


@app.command("show")
def user_show(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
) -> None:
    """Show details for a specific User."""
    run_query(
        get_client(), q.SHOW_USER, {"itemID": itemid}, t.get_show_as_csv,
        nested=NestedLists("user", q.USER_SHOW_CONTINUATIONS),
    )


@app.command("create") 
def user_create(
    email: str = typer.Option(..., "-e", "--email", help="User email address."),
    firstname: str = typer.Option("", "-f", "--firstname", help="First name."),
    lastname: str = typer.Option(..., "-l", "--lastname", help="Last name."),
    role: str = typer.Option(..., "-r", "--role", help=f"Role: {', '.join(VALID_ROLES)}."),
    sendinvite: str = typer.Option("True", "-s", "--sendinvite", help="Send email invitation: true or false."),
) -> None:
    """Create a new User."""
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
    yes: bool = YES_OPTION,
) -> None:
    """Delete a User."""
    client = get_client()
    confirm_delete("User", itemid, yes)
    run_query(client, q.DELETE_USER, {"itemid": itemid}, t.get_delete_as_csv)


@app.command("role")
def user_role(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
    role: str = typer.Option(..., "-r", "--role", help=f"New role: {', '.join(VALID_ROLES)}."),
) -> None:
    """Update a User's role."""
    role_val = validate_user_role(role)
    run_query(
        get_client(),
        q.UPDATE_USER_ROLE,
        {"itemid": itemid, "userRole": role_val},
        t.get_update_role_as_csv,
        nested=NestedLists("user", q.USER_LIST_CONTINUATIONS, at=("userRoleUpdate", "entity")),
    )


@app.command("state")
def user_state(
    itemid: str = typer.Option(..., "-i", "--itemid", help="User ID."),
    state_val: str = typer.Option(..., "-s", "--state", help="New state: ACTIVE or DISABLED."),
) -> None:
    """Update a User's state (active/disabled)."""
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
    """Reset MFA for a User."""
    run_query(get_client(), q.RESET_USER_MFA, {"itemid": itemid}, t.get_reset_mfa_as_csv)
