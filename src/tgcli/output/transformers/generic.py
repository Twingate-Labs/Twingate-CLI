"""Generic transformer utilities — port of the original GenericTransformers.py.

All functions return a pandas DataFrame. Column paths support dot-notation
for one level of nesting (e.g. "remoteNetwork.id").
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_col(node: dict[str, Any], col: str) -> Any:
    """Resolve a column path (possibly dotted) from a node dict."""
    if "." in col:
        parts = col.split(".", 1)
        parent = node.get(parts[0])
        if parent is None:
            logger.debug("Could not find attribute '%s' in node.", parts[0])
            return None
        return parent.get(parts[1]) if isinstance(parent, dict) else None
    return node.get(col)


def _normalise_edges(value: Any) -> Any:
    """If a value is an edges dict, collapse it to a list of IDs."""
    if isinstance(value, dict) and "edges" in value:
        return [el["node"]["id"] for el in value["edges"]]
    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_ids(json_results: dict, object_name: str) -> list[str]:
    """Extract a flat list of IDs from a single-page edges response."""
    edges = json_results["data"][object_name]["edges"]
    return [item["node"]["id"] for item in edges]


def get_ids_and_compare_to_file(
    json_results: dict, ids_file: str, object_name: str
) -> tuple[set[str], set[str]]:
    """Compare IDs in the API response against a file of known IDs."""
    current_ids = set(get_ids(json_results, object_name))
    with open(ids_file) as fh:
        raw = fh.read()
    file_ids = set(
        raw.replace("[", "")
        .replace("]", "")
        .replace("'", "")
        .replace("\n", "")
        .replace(" ", "")
        .split(",")
    )
    file_ids.discard("")
    return current_ids - file_ids, file_ids - current_ids


def get_update_as_csv_no_nesting(
    json_results: dict, objectname: str, columns: list[str]
) -> pd.DataFrame:
    """Transform a single mutation response (ok/error + optional entity fields)."""
    item = json_results["data"][objectname]
    is_ok: bool = item[columns[0]]
    is_error = item[columns[1]]
    datarow: list[Any] = [is_ok, is_error]

    for col in columns[2:]:
        if col == "token":
            continue  # handled separately below
        if is_ok:
            raw: Any = ""
            if "." in col:
                parts = col.split(".", 1)
                if "entity" in item:
                    raw = item["entity"].get(parts[0], {})
                    if isinstance(raw, dict):
                        raw = raw.get(parts[1], "")
            else:
                raw = item.get("entity", {}).get(col, "") if "entity" in item else ""
            datarow.append(_normalise_edges(raw))
        else:
            datarow.append(None)

    if "token" in columns:
        datarow.append(item.get("token"))

    data = [datarow]
    if not is_ok:
        empty = [None] * len(columns)
        empty[0] = is_ok
        empty[1] = is_error
        data = [empty]

    pd.set_option("display.max_rows", None)
    return pd.DataFrame(data, columns=columns)


def get_show_as_csv_no_nesting(
    json_results: dict, objectname: str, columns: list[str]
) -> pd.DataFrame:
    """Transform a single-object show/get query response."""
    item = json_results["data"][objectname]
    datarow: list[Any] = []
    for col in columns:
        if item is not None:
            value = _resolve_col(item, col)
            datarow.append(_normalise_edges(value))
        else:
            datarow.append(None)
    pd.set_option("display.max_rows", None)
    return pd.DataFrame([datarow], columns=columns)


def get_list_as_csv_no_nesting(
    json_results: dict, object_name: str, columns: list[str]
) -> pd.DataFrame:
    """Transform a single-page list query into a DataFrame."""
    edges = json_results["data"][object_name]["edges"]
    data: list[list[Any]] = []
    for item in edges:
        node = item["node"]
        if node is None:
            data.append([None] * len(columns))
            continue
        row = [_normalise_edges(_resolve_col(node, col)) for col in columns]
        data.append(row)
    pd.set_option("display.max_rows", None)
    return pd.DataFrame(data, columns=columns)


def get_list_as_csv(
    json_results: list[list[dict]], columns: list[str]
) -> pd.DataFrame:
    """Transform multi-page paginated results (list of edge-lists) into a DataFrame."""
    data: list[list[Any]] = []
    for page in json_results:
        for item in page:
            node = item["node"]
            if node is None:
                data.append([None] * len(columns))
                continue
            row = [_normalise_edges(_resolve_col(node, col)) for col in columns]
            data.append(row)
    pd.set_option("display.max_rows", None)
    return pd.DataFrame(data, columns=columns)


def check_if_more_pages(json_results: dict, obj_name: str) -> tuple[bool, str | None]:
    """Return (has_next_page, cursor_or_none) for the given object."""
    page_info = json_results["data"][obj_name]["pageInfo"]
    if page_info["hasNextPage"]:
        return True, page_info["endCursor"]
    return False, None
