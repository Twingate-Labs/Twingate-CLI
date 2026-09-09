"""Gateway data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "address", "remoteNetwork.id", "remoteNetwork.name"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "address", "remoteNetwork.id", "remoteNetwork.name"]
    return generic.get_show_as_csv_no_nesting(json_results, "gateway", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "address"]
    return generic.get_update_as_csv_no_nesting(json_results, "gatewayCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "gatewayDelete", columns)


def get_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "address"]
    return generic.get_update_as_csv_no_nesting(json_results, "gatewayUpdate", columns)
