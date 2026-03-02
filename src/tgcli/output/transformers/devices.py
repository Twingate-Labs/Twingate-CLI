"""Device data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = [
        "id", "name", "isTrusted", "osName", "deviceType",
        "lastFailedLoginAt", "lastSuccessfulLoginAt", "user.email",
        "osVersion", "username", "serialNumber", "clientVersion", "activeState",
    ]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "id", "name", "isTrusted", "osName", "deviceType",
        "lastFailedLoginAt", "lastSuccessfulLoginAt", "user.email",
        "osVersion", "hardwareModel", "hostname", "username",
        "serialNumber", "activeState", "clientVersion", "manufacturerName",
    ]
    return generic.get_show_as_csv_no_nesting(json_results, "device", columns)


def get_update_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "isTrusted", "activeState"]
    return generic.get_update_as_csv_no_nesting(json_results, "deviceUpdate", columns)


def get_block_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "isTrusted", "activeState"]
    return generic.get_update_as_csv_no_nesting(json_results, "deviceBlock", columns)


def get_unblock_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "isTrusted", "activeState"]
    return generic.get_update_as_csv_no_nesting(json_results, "deviceUnblock", columns)


def get_archive_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "isTrusted", "activeState"]
    return generic.get_update_as_csv_no_nesting(json_results, "deviceArchive", columns)


def get_sn_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "serialNumber", "createdAt", "matchedDevices"]
    return generic.get_list_as_csv(json_results, columns)


def get_add_serial_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "serialNumbersCreate", columns)


def get_remove_serial_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "serialNumbersDelete", columns)
