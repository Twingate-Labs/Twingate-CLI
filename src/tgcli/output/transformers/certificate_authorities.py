"""Certificate authority data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic

TYPE_LABELS = {"X509CertificateAuthority": "X509", "SSHCertificateAuthority": "SSH"}
_QUERY_COLUMNS = ["__typename", "id", "name", "fingerprint"]
_COLUMNS = ["type", "id", "name", "fingerprint"]


def _label_types(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = _COLUMNS
    df["type"] = df["type"].map(lambda t: TYPE_LABELS.get(t, t))
    return df


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    return _label_types(generic.get_list_as_csv(json_results, _QUERY_COLUMNS))


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    return _label_types(generic.get_show_as_csv_no_nesting(json_results, "certificateAuthority", _QUERY_COLUMNS))


def get_create_x509_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(
        json_results, "x509CertificateAuthorityCreate", ["ok", "error", "id", "name", "fingerprint"]
    )


def get_create_ssh_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(
        json_results, "sshCertificateAuthorityCreate", ["ok", "error", "id", "name", "fingerprint"]
    )


def get_delete_x509_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(json_results, "x509CertificateAuthorityDelete", ["ok", "error"])


def get_delete_ssh_as_csv(json_results: dict) -> pd.DataFrame:
    return generic.get_update_as_csv_no_nesting(json_results, "sshCertificateAuthorityDelete", ["ok", "error"])
