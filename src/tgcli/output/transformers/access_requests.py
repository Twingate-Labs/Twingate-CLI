"""Access request data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "status", "requestor.email", "resource.name", "createdAt", "updatedAt"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "status", "requestor.email", "resource.name", "createdAt", "updatedAt"]
    return generic.get_show_as_csv_no_nesting(json_results, "accessRequest", columns)


def get_approve_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "accessRequestApprove", columns)


def get_reject_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "accessRequestReject", columns)
