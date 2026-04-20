"""DNS security data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "allowedDomains", "deniedDomains"]
    return generic.get_show_as_csv_no_nesting(json_results, "dnsFilteringProfile", columns)


def get_update_allow_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(
        json_results, "dnsFilteringAllowedDomainsSet", columns
    )


def get_update_deny_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(
        json_results, "dnsFilteringDeniedDomainsSet", columns
    )
