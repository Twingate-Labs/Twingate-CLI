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


def get_posture_as_csv(json_results: dict) -> pd.DataFrame:
    posture = json_results.get("data", {}).get("devicePosture") or {}
    rows = []

    for check in ["hardDriveEncryption", "screenLockPasscode", "firewall", "biometric", "antivirus"]:
        d = posture.get(check) or {}
        data.append([check, d.get("isSatisfied"), str(d.get("detected"))])

    os_data = posture.get("osVersion") or {}
    data.append(["osVersion", os_data.get("isSatisfied"), os_data.get("version")])

    for check in ["crowdstrike", "jamf", "kandji", "inTune", "sentinelOne", "onePassword"]:
        d = posture.get(check) or {}
        if d:
            detail = d.get("failureReason") or d.get("failureDetails") or d.get("expiredAt") or ""
            data.append([check, str(d.get("isVerified")), detail])

    manual = posture.get("manualVerification") or {}
    if manual:
        data.append(["manualVerification", str(manual.get("isVerified")), manual.get("value") or ""])

    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_colwidth", None)
    pd.set_option("display.width", None)
    return pd.DataFrame(data, columns=columns)
