"""Gateway data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


COLUMNS = [
    "id", "address", "remoteNetwork.name", "remoteNetwork.id",
    "x509CA.name", "x509CA.fingerprint", "sshCA.name", "sshCA.fingerprint",
]
MUTATION_COLUMNS = ["ok", "error", "id", "address", "remoteNetwork.name", "x509CA.name", "sshCA.name"]


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    return generic.get_list_as_csv(json_results, COLUMNS)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_show_as_csv_no_nesting(json_results, "gateway", COLUMNS)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(json_results, "gatewayCreate", MUTATION_COLUMNS)


def get_update_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(json_results, "gatewayUpdate", MUTATION_COLUMNS)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(json_results, "gatewayDelete", ["ok", "error"])
