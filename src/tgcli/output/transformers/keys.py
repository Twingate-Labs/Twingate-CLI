"""Service account key data transformers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from tgcli.output.transformers import generic


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "expiresAt", "revokedAt", "status"]
    return generic.get_show_as_csv_no_nesting(json_results, "serviceAccountKey", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "expiresAt", "status", "token"]
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


def get_list_as_csv(
    json_results: list,
    status_filter: str | None = None,
    expiring_days: int | None = None,
) -> pd.DataFrame:
    """Flatten all keys from all service accounts into a single DataFrame.

    Optionally filter by status or by keys expiring within a given number of days.
    """
    columns = ["serviceAccountId", "serviceAccountName", "id", "name", "status", "createdAt", "expiresAt", "revokedAt"]
    rows: list[list[Any]] = []
    now = datetime.now(tz=timezone.utc)

    for page in json_results:
        for edge in page:
            account = edge["node"]
            if account is None:
                continue
            sa_id = account.get("id", "")
            sa_name = account.get("name", "")
            for key_edge in account.get("keys", {}).get("edges", []):
                key = key_edge["node"]
                if key is None:
                    continue

                if status_filter and key.get("status") != status_filter:
                    continue

                if expiring_days is not None:
                    expires_at = key.get("expiresAt")
                    if not expires_at:
                        continue
                    try:
                        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    delta = (expiry - now).days
                    if delta < 0 or delta > expiring_days:
                        continue

                rows.append([
                    sa_id,
                    sa_name,
                    key.get("id", ""),
                    key.get("name", ""),
                    key.get("status", ""),
                    key.get("createdAt", ""),
                    key.get("expiresAt", ""),
                    key.get("revokedAt", ""),
                ])

    pd.set_option("display.max_rows", None)
    return pd.DataFrame(rows, columns=columns)
