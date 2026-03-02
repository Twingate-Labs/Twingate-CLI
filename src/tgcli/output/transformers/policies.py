"""Security policy data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "name", "policyType"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "policyType", "groups"]
    return generic.get_show_as_csv_no_nesting(json_results, "securityPolicy", columns)
