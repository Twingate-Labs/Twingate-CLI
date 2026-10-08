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


def _approver_group_names(json_results: dict) -> list[str] | None:
    """Approver group names in the same order as the approverGroups IDs, or None when the resource wasn't found."""
    resource = (json_results.get("data") or {}).get("resource")
    if resource is None:
        return None
    edges = (resource.get("approverGroups") or {}).get("edges") or []
    return [edge["node"]["name"] for edge in edges]


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = [
        "id", "name", "isActive", "remoteNetwork.id",
        "address.type", "address.value", "access.edges",
        "securityPolicy.id", "alias", "isVisible",
        "isBrowserShortcutEnabled", "routingMode", "tags",
    ]
    # "type" goes last so scripts reading the existing columns by position keep working.
    return _label_type(generic.get_list_as_csv(json_results, columns + ["__typename"]))


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "id", "name", "isActive", "remoteNetwork.id",
        "address.type", "address.value",
        "protocols.allowIcmp", "protocols.tcp.policy", "protocols.udp.policy",
        "isVisible", "isBrowserShortcutEnabled", "routingMode",
    ]
    # type, then the fields only some resource types have (blank otherwise), all after the original columns.
    extra = [
        "__typename", "accessPolicy.mode", "accessPolicy.durationSeconds",
        "gateway.id", "gateway.address", "clusterRef",
        "upstream.port", "upstream.tlsMode", "downstream.port", "downstream.tlsMode",
        "approvalMode", "approverGroups",
    ]
    df = _label_type(generic.get_show_as_csv_no_nesting(json_results, "resource", columns + extra))
    df["approverGroupNames"] = [_approver_group_names(json_results)]
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
