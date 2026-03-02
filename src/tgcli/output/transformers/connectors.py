"""Connector data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = [
        "id", "name", "state", "hostname", "version",
        "publicIP", "lastHeartbeatAt", "hasStatusNotificationsEnabled",
    ]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "id", "name", "lastHeartbeatAt",
        "hasStatusNotificationsEnabled", "state",
        "remoteNetwork.id", "remoteNetwork.name",
    ]
    return generic.get_show_as_csv_no_nesting(json_results, "connector", columns)


def get_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "hasStatusNotificationsEnabled"]
    return generic.get_update_as_csv_no_nesting(json_results, "connectorUpdate", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "entity.id", "entity.name"]
    return generic.get_show_as_csv_no_nesting(json_results, "connectorCreate", columns)


def get_gen_tokens_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "connectorTokens.accessToken", "connectorTokens.refreshToken"]
    return generic.get_show_as_csv_no_nesting(json_results, "connectorGenerateTokens", columns)
