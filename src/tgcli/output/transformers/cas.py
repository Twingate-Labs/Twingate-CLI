"""Certificate authority data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = ["id", "name", "type", "createdAt", "updatedAt"]
    return generic.get_list_as_csv(json_results, columns)


def get_show_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["id", "name", "type", "createdAt", "updatedAt"]
    return generic.get_show_as_csv_no_nesting(json_results, "certificateAuthority", columns)


def get_create_ssh_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "type"]
    return generic.get_update_as_csv_no_nesting(json_results, "sshCertificateAuthorityCreate", columns)


def get_delete_ssh_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "sshCertificateAuthorityDelete", columns)


def get_create_x509_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error", "id", "name", "type"]
    return generic.get_update_as_csv_no_nesting(json_results, "x509CertificateAuthorityCreate", columns)


def get_delete_x509_as_csv(json_results: dict) -> pd.DataFrame:
    columns = ["ok", "error"]
    return generic.get_update_as_csv_no_nesting(json_results, "x509CertificateAuthorityDelete", columns)
