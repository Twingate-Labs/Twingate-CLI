"""Service account key data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "expiresAt", "revokedAt", "status"]
    return generic.get_show_as_csv_no_nesting(json_results, "serviceAccountKey", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "token", "id", "name", "expiresAt", "status"]
    return generic.get_update_as_csv_no_nesting(json_results, "serviceAccountKeyCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "serviceAccountKeyDelete", columns)


def get_revoke_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "serviceAccountKeyRevoke", columns)


def get_rename_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, "serviceAccountKeyUpdate", columns)
