"""Group data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "name", "isActive", "type", "users", "resources"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "isActive", "type", "users", "resources"]
    return generic.get_show_as_csv_no_nesting(json_results, "group", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "resources", "users"]
    return generic.get_update_as_csv_no_nesting(json_results, "groupCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "groupDelete", columns)


def get_add_remove_users_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "users"]
    return generic.get_update_as_csv_no_nesting(json_results, "groupUpdate", columns)


def get_add_remove_resources_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "resources"]
    return generic.get_update_as_csv_no_nesting(json_results, "groupUpdate", columns)


def get_assign_policy_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "ok", "error", "id", "name",
        "securityPolicy.id", "securityPolicy.name", "securityPolicy.policyType",
    ]
    return generic.get_update_as_csv_no_nesting(json_results, "groupUpdate", columns)
