"""Access request data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic

COLUMNS = [
    "id", "status", "requestedAt", "user.email", "user.id",
    "resource.name", "resource.id", "reason",
]


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    return generic.get_list_as_csv(json_results, COLUMNS)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_show_as_csv_no_nesting(json_results, "accessRequest", COLUMNS)


def get_approve_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(json_results, "accessRequestApprove", ["ok", "error"])


def get_reject_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(json_results, "accessRequestReject", ["ok", "error"])
