"""Utility functions for FQDN matching and resource-definition ordering.

Port of ``libs/TGUtils.py`` from the original monolithic CLI.
Used by the ``mappings user-resource`` command when an --fqdn argument is
supplied to determine which resource definitions match a given FQDN and which
definitions are more specific than others.
"""

from __future__ import annotations

import re

import pandas as pd


def does_addr_match_res_definition(resource_definition: str, addr: str) -> bool:
    """Return True if *addr* matches the glob-style *resource_definition*.

    ``*`` → ``.*`` and ``?`` → ``.?`` in regex terms; ``.`` is escaped.
    """
    regex_definition = (
        resource_definition.replace(".", r"\.")
        .replace("*", ".*")
        .replace("?", ".?")
    )
    return bool(re.search(regex_definition, addr))


def _get_number_of_tlds_after_last_meta_char(res_definition: str) -> int:
    """Return the number of TLD segments after the last ``*`` or ``?``."""
    meta_chars = ["?", "*"]
    pos_list = [res_definition.rfind(c) for c in meta_chars]
    last_meta_char_pos = max(pos_list)
    post_meta = res_definition[last_meta_char_pos + 1 :]
    tlds = post_meta.split(".")
    return len(tlds)


def _get_number_of_chars_before_first_meta_char(res_definition: str) -> int:
    """Return the number of characters before the first ``*`` or ``?``."""
    meta_chars = ["?", "*"]
    pos_list = [res_definition.rfind(c) for c in meta_chars]
    valid_positions = [i for i in pos_list if i > -1]
    if not valid_positions:
        return len(res_definition)
    return min(valid_positions)


def resource_definition_matcher(res_definition_list: list[str]) -> dict[str, dict]:
    """Return an ordered dict mapping each definition to its specificity scores.

    The dict is sorted from most-specific (highest scores) to least-specific.
    Scores:
      - ``nb_of_tlds``: TLD count after the last meta-char (higher = more specific)
      - ``nb_of_chars``: char count before the first meta-char (higher = more specific)
    """
    scores: dict[str, dict] = {}
    for res in res_definition_list:
        nb_of_tlds = _get_number_of_tlds_after_last_meta_char(res)
        nb_of_chars = _get_number_of_chars_before_first_meta_char(res)
        scores[res] = {"nb_of_tlds": nb_of_tlds, "nb_of_chars": nb_of_chars}

    sorted_keys = sorted(
        scores,
        key=lambda x: (scores[x]["nb_of_tlds"], scores[x]["nb_of_chars"]),
        reverse=True,
    )
    return {k: scores[k] for k in sorted_keys}


def resource_definition_matcher2(df: pd.DataFrame) -> pd.DataFrame:
    """Re-order *df* rows by resource-definition specificity.

    *df* must contain ``id`` and ``address.value`` columns.
    Returns a new DataFrame ordered from most-specific to least-specific,
    with duplicate ``id`` rows dropped.
    """
    scores: dict[str, dict] = {}
    for _, row in df.iterrows():
        res = row["address.value"]
        resid = row["id"]
        nb_of_tlds = _get_number_of_tlds_after_last_meta_char(res)
        nb_of_chars = _get_number_of_chars_before_first_meta_char(res)
        scores[resid] = {"nb_of_tlds": nb_of_tlds, "nb_of_chars": nb_of_chars}

    sorted_keys = sorted(
        scores,
        key=lambda x: (scores[x]["nb_of_tlds"], scores[x]["nb_of_chars"]),
        reverse=True,
    )

    df = df.drop_duplicates("id")
    df = df.set_index("id")
    df = df.reindex(sorted_keys)
    return df


def detect_res_definition_ambiguity(
    scores: dict[str, dict],
) -> tuple[int, list[str]]:
    """Detect ambiguous resource-definition pairs.

    Two definitions are ambiguous when they share identical specificity scores
    (same ``nb_of_tlds`` and ``nb_of_chars``).

    Returns ``(count, pairs)`` where each entry in *pairs* is a string
    ``"def_a|def_b"``.
    """
    seen_scores: list[dict] = []
    seen_res: list[str] = []
    nb_of_ambiguities = 0
    ambiguity_list: list[str] = []

    for key, score in scores.items():
        if score not in seen_scores:
            seen_scores.append(score)
            seen_res.append(key)
        else:
            idx = seen_scores.index(score)
            nb_of_ambiguities += 1
            ambiguity_list.append(f"{key}|{seen_res[idx]}")

    return nb_of_ambiguities, ambiguity_list
