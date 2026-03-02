"""Resource data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = [
        "id", "name", "isActive", "remoteNetwork.id",
        "address.type", "address.value", "access.edges",
        "securityPolicy.id", "alias", "isVisible",
        "isBrowserShortcutEnabled", "tags",
    ]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "id", "name", "isActive", "remoteNetwork.id",
        "address.type", "address.value",
        "protocols.allowIcmp", "protocols.tcp.policy", "protocols.udp.policy",
        "isVisible", "isBrowserShortcutEnabled",
    ]
    return generic.get_show_as_csv_no_nesting(json_results, "resource", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceDelete", columns)


def get_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "ok", "error", "id", "name",
        "remoteNetwork.id", "remoteNetwork.name",
        "address.type", "address.value", "alias",
    ]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_visibility_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "isVisible", "isBrowserShortcutEnabled"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_alias_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "alias"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_policy_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "securityPolicy.id"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_autolock_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "ok", "error", "id", "name",
        "usageBasedAutolockDurationDays", "approvalMode",
    ]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_access_update_as_csv(json_results: dict, mutation_name: str) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, mutation_name, columns)
