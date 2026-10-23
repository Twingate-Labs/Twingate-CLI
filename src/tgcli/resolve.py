"""Let options that take an ID also take a name: Group, Remote Network, Security Policy, Service Account.

A value that is already an ID is passed through untouched with no request, so scripts keep working at the same speed.
Anything else is looked up by exact, case-sensitive name, one request per kind however many names there are. A name that
matches nothing, or more than one object, is an error: the CLI never guesses, because these values feed writes.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any, NamedTuple

from tgcli.pagination import fetch_connection


class Kind(NamedTuple):
    label: str  # how it appears in messages
    plural: str
    root: str  # the GraphQL collection to look names up in


GROUP = Kind("group", "groups", "groups")
NETWORK = Kind("Remote Network", "Remote Networks", "remoteNetworks")
POLICY = Kind("Security Policy", "Security Policies", "securityPolicies")
SERVICE_ACCOUNT = Kind("Service Account", "Service Accounts", "serviceAccounts")


class ResolveError(Exception):
    """One or more values could not be turned into exactly one ID. ``problems`` has one message per value."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


_BASE64 = re.compile(r"[A-Za-z0-9+/]{4,}={0,2}")
_DECODED_ID = re.compile(r"[A-Za-z]+:[A-Za-z0-9-]+")


def looks_like_id(value: str) -> bool:
    """True for a Twingate ID: base64 of "<Type>:<number or UUID>".

    This only decides whether to skip a name lookup. It never reads anything out of an ID. A name that happens to
    be valid base64 of that shape would be treated as an ID, which is vanishingly unlikely.
    """
    if not _BASE64.fullmatch(value) or len(value) % 4:
        return False
    try:
        return _DECODED_ID.fullmatch(base64.b64decode(value, validate=True).decode("ascii")) is not None
    except (binascii.Error, UnicodeDecodeError):
        return False


def _lookup(client: Any, kind: Kind, names: list[str]) -> dict[str, list[str]]:
    query = (
        f"query($cursor: String, $names: [String!]) {{ {kind.root}(after: $cursor, filter: {{name: {{in: $names}}}}) "
        "{ pageInfo { hasNextPage endCursor } edges { node { id name } } } }"
    )
    edges, _, _ = fetch_connection(client, query, {"names": names}, [kind.root])
    found: dict[str, list[str]] = {}
    for edge in edges:
        found.setdefault(edge["node"]["name"], []).append(edge["node"]["id"])
    return found


def resolve(client: Any, kind: Kind, values: list[str]) -> list[str]:
    """The ID for each value, in the same order (repeats included).

    Raises ResolveError listing every value that matched nothing or was ambiguous, so one run reports everything.
    API and authentication errors from the lookup propagate unchanged.
    """
    names = list(dict.fromkeys(v for v in values if not looks_like_id(v)))
    found = _lookup(client, kind, names) if names else {}
    problems: list[str] = []
    for name in names:
        ids = found.get(name, [])
        if not ids:
            problems.append(
                f"no {kind.label} named '{name}' (a name must match exactly, including capitals; you can also pass the ID)"
            )
        elif len(ids) > 1:
            problems.append(f"'{name}' matches {len(ids)} {kind.plural} ({', '.join(ids)}); use the ID of the one you mean")
    if problems:
        raise ResolveError(problems)
    return [v if looks_like_id(v) else found[v][0] for v in values]
