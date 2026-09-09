"""DNS security data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "allowedDomains", "deniedDomains"]
    return generic.get_show_as_csv_no_nesting(json_results, "dnsFilteringProfile", columns)


def get_update_allow_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "allowedDomains", "deniedDomains"]
    return generic.get_update_as_csv_no_nesting(
        json_results, "dnsFilteringProfileUpdate", columns
    )


def get_update_deny_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "allowedDomains", "deniedDomains"]
    return generic.get_update_as_csv_no_nesting(
        json_results, "dnsFilteringProfileUpdate", columns
    )


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name"]
    return generic.get_update_as_csv_no_nesting(json_results, "dnsFilteringProfileCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "dnsFilteringProfileDelete", columns)
