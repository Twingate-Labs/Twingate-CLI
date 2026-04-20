"""Service account data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "name", "createdAt", "updatedAt", "keys", "resources"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "keys", "resources"]
    return generic.get_show_as_csv_no_nesting(json_results, "serviceAccount", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, "serviceAccountCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "serviceAccountDelete", columns)


def get_add_remove_resources_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "resources"]
    return generic.get_update_as_csv_no_nesting(json_results, "serviceAccountUpdate", columns)
