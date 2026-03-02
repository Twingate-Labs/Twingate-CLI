"""User data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "firstName", "lastName", "email", "role", "state", "groups"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "firstName", "lastName", "email", "role", "state", "groups"]
    return generic.get_show_as_csv_no_nesting(json_results, "user", columns)


def get_update_role_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "firstName", "lastName", "email", "role", "state", "groups"]
    return generic.get_update_as_csv_no_nesting(json_results, "userRoleUpdate", columns)


def get_update_state_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "firstName", "lastName", "email", "role", "state"]
    return generic.get_update_as_csv_no_nesting(json_results, "userDetailsUpdate", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "firstName", "lastName", "email", "role", "state"]
    return generic.get_update_as_csv_no_nesting(json_results, "userCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "userDelete", columns)


def get_reset_mfa_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "userResetMfa", columns)
