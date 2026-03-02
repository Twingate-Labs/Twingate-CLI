"""User-to-resource mapping analytics commands."""

from __future__ import annotations

import json
import logging
from typing import Optional

import pandas as pd
import typer

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.commands._common import get_client
from tgcli.main import state
from tgcli.queries import mappings as q

app = typer.Typer(help="Analyse user-to-resource and user-to-network mappings.")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# user-network
# ---------------------------------------------------------------------------

@app.command("user-network")
def user_network() -> None:
    """Show all users and the remote networks / resources they can access."""
    client = get_client()
    cursor = "0"
    has_next = True
    all_users: list[list] = []

    try:
        while has_next:
            result = client.execute(q.LIST_USER_RN_MAPPINGS, {"cursor": cursor})
            page = result["data"]["users"]
            all_users.append(page["edges"])
            page_info = page["pageInfo"]
            has_next = page_info.get("hasNextPage", False)
            if has_next:
                cursor = page_info["endCursor"]
    except TwingateAuthError as exc:
        typer.echo(f"Authentication error: {exc}", err=True)
        raise typer.Exit(1)
    except TwingateAPIError as exc:
        typer.echo(f"API error: {exc}", err=True)
        raise typer.Exit(1)

    user_info: list[dict] = []
    for page in all_users:
        for user_edge in page:
            node = user_edge["node"]
            username = node["email"]
            all_rns: list[str] = []
            all_resources: list[str] = []
            for grp_edge in node.get("groups", {}).get("edges", []):
                for res_edge in grp_edge["node"].get("resources", {}).get("edges", []):
                    res_node = res_edge["node"]
                    rn_name = res_node["remoteNetwork"]["name"]
                    res_name = res_node["name"]
                    if rn_name not in all_rns:
                        all_rns.append(rn_name)
                    if res_name not in all_resources:
                        all_resources.append(res_name)
            user_info.append({
                "user.email": username,
                "networks.count": len(all_rns),
                "resources.count": len(all_resources),
                "networks": all_rns,
                "resources": all_resources,
            })

    df = pd.json_normalize(user_info)
    fmt = state.output_format.upper()
    if fmt == "CSV":
        typer.echo(df.to_csv(index=False))
    elif fmt == "DF":
        typer.echo(df.to_string())
    else:
        typer.echo(json.dumps(user_info, indent=2, default=str))


# ---------------------------------------------------------------------------
# user-resource
# ---------------------------------------------------------------------------

@app.command("user-resource")
def user_resource(
    email: str = typer.Option(..., "-e", "--email", help="User email address."),
    fqdn: str = typer.Option("", "-f", "--fqdn", help="FQDN to match against resource definitions."),
) -> None:
    """Show resources accessible to a specific user (optionally matched against an FQDN)."""
    client = get_client()

    # 1. Resolve user → group IDs
    try:
        user_result = client.execute(q.GET_USER_BY_EMAIL, {"userEmail": email})
    except (TwingateAuthError, TwingateAPIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    edges = user_result["data"]["users"]["edges"]
    if not edges:
        typer.echo(f"No user found with email '{email}'.")
        raise typer.Exit(0)

    group_ids = [
        grp["node"]["id"]
        for grp in edges[0]["node"].get("groups", {}).get("edges", [])
    ]

    # 2. Collect resources across all groups
    all_resources: list[dict] = []
    for gid in group_ids:
        cursor = "0"
        has_next = True
        try:
            while has_next:
                res_result = client.execute(
                    q.GET_GROUP_RESOURCES, {"cursor": cursor, "groupID": gid}
                )
                group_data = res_result["data"]["group"]
                resources_page = group_data["resources"]
                for res_edge in resources_page["edges"]:
                    res_node = res_edge["node"]
                    res_node["group.id"] = group_data["id"]
                    res_node["group.name"] = group_data["name"]
                    all_resources.append(res_node)
                page_info = resources_page["pageInfo"]
                has_next = page_info.get("hasNextPage", False)
                if has_next:
                    cursor = page_info["endCursor"]
        except (TwingateAuthError, TwingateAPIError) as exc:
            typer.echo(f"Error fetching resources for group {gid}: {exc}", err=True)
            raise typer.Exit(1)

    df = pd.json_normalize(all_resources)
    fmt = state.output_format.upper()

    if fqdn and not df.empty:
        # Import TGUtils lazily to avoid hard dependency at module load time
        from tgcli.utils.tg_utils import (
            detect_res_definition_ambiguity,
            does_addr_match_res_definition,
            resource_definition_matcher,
            resource_definition_matcher2,
        )

        df["matchFqdn"] = df["address.value"].apply(
            does_addr_match_res_definition, args=(fqdn,)
        )
        df_matches = df.loc[df["matchFqdn"]]
        df_duplicates = df_matches[df_matches.duplicated(["id"])]
        ordered = resource_definition_matcher2(df_matches) if not df_matches.empty else df_matches
        ordered2 = resource_definition_matcher(df_matches["address.value"].tolist()) if not df_matches.empty else {}
        nb_ambig, ambig_list = detect_res_definition_ambiguity(ordered2)

        _print_section("All Resources available for User", df, fmt)
        _print_section("Resources matching FQDN", df_matches, fmt)
        _print_section("Ordered list of Resources", ordered, fmt)
        _print_section("Duplicate Resources (served by more than 1 Group)", df_duplicates, fmt)

        if nb_ambig > 0:
            typer.echo(f"\nConflicting resource definition pairs: {ambig_list}")
        else:
            typer.echo("\nNo conflicting resource definitions found.")
    else:
        _print_section("Resources available for User", df, fmt)


def _print_section(title: str, df: pd.DataFrame, fmt: str) -> None:
    typer.echo(f"\n{title}:")
    if df.empty:
        typer.echo("  None")
    elif fmt == "CSV":
        typer.echo(df.to_csv(index=False))
    else:
        typer.echo(df.to_string())
