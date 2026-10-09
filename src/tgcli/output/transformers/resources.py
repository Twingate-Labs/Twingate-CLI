"""Resource data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


TYPE_LABELS = {
    "NetworkResource": "NETWORK",
    "SSHResource": "SSH",
    "WebAppResource": "WEB_APP",
    "KubernetesResource": "KUBERNETES",
}


def _label_type(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"__typename": "type"})
    df["type"] = df["type"].map(lambda t: TYPE_LABELS.get(t, t))
    return df


# type, then the fields only some resource types have (blank otherwise). Always placed after a command's
# original columns so scripts reading those by position keep working.
_TYPE_AND_EXTRA_COLUMNS = [
    "__typename", "accessPolicy.mode", "accessPolicy.durationSeconds",
    "gateway.id", "gateway.address", "clusterRef",
    "upstream.port", "upstream.tlsMode", "downstream.port", "downstream.tlsMode",
    "approvalMode", "approverGroups",
]


_INT_COLUMNS = ["accessPolicy.durationSeconds", "upstream.port", "downstream.port"]


def _keep_ints(df: pd.DataFrame) -> pd.DataFrame:
    """Stop pandas turning int columns with missing values into floats (443 -> 443.0). Missing stays None."""
    for col in _INT_COLUMNS:
        df[col] = pd.Series([None if pd.isna(v) else int(v) for v in df[col]], dtype=object, index=df.index)
    return df


def _approver_names_of(resource: dict | None) -> list[str] | None:
    """Approver group names in the same order as the approverGroups IDs, or None when there is no resource."""
    if resource is None:
        return None
    edges = (resource.get("approverGroups") or {}).get("edges") or []
    return [edge["node"]["name"] for edge in edges]


_LIST_COLUMNS = [
    "id", "name", "isActive", "remoteNetwork.id",
    "address.type", "address.value", "access.edges",
    "securityPolicy.id", "alias", "isVisible",
    "isBrowserShortcutEnabled", "routingMode", "tags",
]


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    # "type" goes last so scripts reading the original columns by position keep working.
    return _label_type(generic.get_list_as_csv(json_results, _LIST_COLUMNS + ["__typename"]))


def get_list_detail_as_csv(json_results: list) -> pd.DataFrame:
    """The default list columns plus everything in _TYPE_AND_EXTRA_COLUMNS and the approver group names."""
    df = _keep_ints(_label_type(generic.get_list_as_csv(json_results, _LIST_COLUMNS + _TYPE_AND_EXTRA_COLUMNS)))
    # One entry per row, in the same order generic.get_list_as_csv emits them (including null nodes).
    df["approverGroupNames"] = [_approver_names_of(edge["node"]) for page in json_results for edge in page]
    return df


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "id", "name", "isActive", "remoteNetwork.id",
        "address.type", "address.value",
        "protocols.allowIcmp", "protocols.tcp.policy", "protocols.udp.policy",
        "isVisible", "isBrowserShortcutEnabled", "routingMode",
    ]
    df = _keep_ints(_label_type(generic.get_show_as_csv_no_nesting(json_results, "resource", columns + _TYPE_AND_EXTRA_COLUMNS)))
    df["approverGroupNames"] = [_approver_names_of((json_results.get("data") or {}).get("resource"))]
    return df


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "routingMode"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceDelete", columns)


def get_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "ok", "error", "id", "name",
        "remoteNetwork.id", "remoteNetwork.name",
        "address.type", "address.value", "alias",
    ]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_visibility_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "isVisible", "isBrowserShortcutEnabled"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_alias_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "alias"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_policy_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "securityPolicy.id"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_routing_mode_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "routingMode"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_autolock_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "ok", "error", "id", "name",
        "usageBasedAutolockDurationDays", "approvalMode",
    ]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_active_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "isActive"]
    return generic.get_update_as_csv_no_nesting(json_results, "resourceUpdate", columns)


def get_access_update_as_csv(json_results: dict, mutation_name: str) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, mutation_name, columns)
