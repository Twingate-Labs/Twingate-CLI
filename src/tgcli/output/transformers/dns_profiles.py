"""DNS Filtering profile data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: dict) -> pd.DataFrame:
    """Transform the (non-paginated) dnsFilteringProfiles list into a DataFrame."""
    columns = ["id", "name", "priority"]
    profiles = json_results["data"]["dnsFilteringProfiles"]
    data = [[profile.get(col) for col in columns] for profile in profiles]
    pd.set_option("display.max_rows", None)
    return pd.DataFrame(data, columns=columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = [
        "id",
        "name",
        "priority",
        "fallbackMethod",
        "allowedDomains",
        "deniedDomains",
        "groups",
    ]
    return generic.get_show_as_csv_no_nesting(json_results, "dnsFilteringProfile", columns)


def get_create_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "priority"]
    return generic.get_update_as_csv_no_nesting(json_results, "dnsFilteringProfileCreate", columns)


def get_delete_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "dnsFilteringProfileDelete", columns)
