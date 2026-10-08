"""Transformers for SSH, web app and Kubernetes resource mutations."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic

_BASE = ["ok", "error", "id", "name", "address.value", "isActive", "isVisible", "remoteNetwork.name", "gateway.id"]
_PORTS = ["upstream.port", "downstream.port"]
_PORTS_TLS = ["upstream.port", "upstream.tlsMode", "downstream.port", "downstream.tlsMode"]


def _transform(field: str, extra: list[str]):
    def transform(json_results: dict) -> pd.DataFrame:
        return generic.get_update_as_csv_no_nesting(json_results, field, _BASE + extra)

    return transform


get_create_ssh_as_csv = _transform("sshResourceCreate", _PORTS)
get_update_ssh_as_csv = _transform("sshResourceUpdate", _PORTS)
get_create_webapp_as_csv = _transform("webAppResourceCreate", _PORTS_TLS)
get_update_webapp_as_csv = _transform("webAppResourceUpdate", _PORTS_TLS)
get_create_k8s_as_csv = _transform("kubernetesResourceCreate", ["clusterRef"] + _PORTS)
get_update_k8s_as_csv = _transform("kubernetesResourceUpdate", ["clusterRef"] + _PORTS)
