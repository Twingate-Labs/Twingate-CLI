"""Remote network data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "name", "isActive", "resources", "connectors"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "isActive", "resources", "connectors"]
    return generic.get_show_as_csv_no_nesting(json_results, "remoteNetwork", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, "remoteNetworkCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "remoteNetworkDelete", columns)


def get_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, "remoteNetworkUpdate", columns)
