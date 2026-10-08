"""Gateway data transformers."""

from __future__ import annotations

import pandas as pd

from tgcli.output.transformers import generic


def get_list_as_csv(json_results: list) -> pd.DataFrame:
    columns = [
        "id", "address", "remoteNetwork.name", "remoteNetwork.id",
        "x509CA.name", "x509CA.fingerprint", "sshCA.name", "sshCA.fingerprint",
    ]
    return generic.get_list_as_csv(json_results, columns)
