"""Shell completion for tgcli.

These functions run every time the user presses TAB, so they must be quick and must never print or raise: when
something goes wrong the right behaviour is to offer nothing, not to write an error into the user's command line.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests
import typer

from tgcli.client.session import SessionManager

_IS_WINDOWS = os.name == "nt"
CACHE_TTL_SECONDS = 120
FETCH_BUDGET_SECONDS = 3.0

GROUPS_QUERY = (
    "query($cursor: String) { groups(after: $cursor) { pageInfo { hasNextPage endCursor } "
    "edges { node { id name type isActive } } } }"
)


def complete_session(incomplete: str) -> list[str]:
    """Saved session names (read from the local keychain, so no network call)."""
    try:
        return sorted(name for name in SessionManager.list_sessions() if name.startswith(incomplete))
    except Exception:
        return []


def _cache_dir() -> Path:
    if _IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "tgcli"


def _cache_file(session: str, url: str) -> Path:
    key = hashlib.sha256(f"{session}\0{url}".encode()).hexdigest()[:16]
    return _cache_dir() / f"groups-{key}.json"


def _read_cache(path: Path) -> tuple[list[dict], float] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data["groups"]), float(data["fetched"])
    except Exception:
        return None


def _write_cache(path: Path, groups: list[dict]) -> None:
    """Best effort. The cache holds group names and IDs for this tenant, so it is private to the user."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"fetched": time.time(), "groups": groups}, handle)
        os.replace(tmp, path)
    except Exception:
        pass


def _fetch_groups(url: str, headers: dict, budget: float) -> list[dict] | None:
    """Every group, or None if it could not all be read within the time budget.

    Deliberately not TwingateClient.execute: that sleeps 30 s or more when the API rate-limits, which would freeze the
    shell on TAB. Any problem, including a 429, simply means "offer nothing" here.
    """
    deadline = time.monotonic() + budget
    groups: list[dict] = []
    cursor = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        response = requests.post(url, json={"query": GROUPS_QUERY, "variables": {"cursor": cursor}}, headers=headers, timeout=remaining)
        body = response.json()
        if response.status_code != 200 or body.get("errors"):
            return None
        connection = body["data"]["groups"]
        groups.extend(edge["node"] for edge in connection["edges"])
        if not connection["pageInfo"]["hasNextPage"]:
            return groups
        cursor = connection["pageInfo"]["endCursor"]


def _groups_for(session: str) -> list[dict]:
    from tgcli.client.client import TwingateClient

    client = TwingateClient(session)
    path = _cache_file(session, client.url)
    cached = _read_cache(path)
    if cached and time.time() - cached[1] < CACHE_TTL_SECONDS:
        return cached[0]
    try:
        fetched = _fetch_groups(client.url, client._headers(), FETCH_BUDGET_SECONDS)
    except Exception:  # no network, a timeout, a malformed reply...
        fetched = None
    if fetched is not None:
        _write_cache(path, fetched)
        return fetched
    return cached[0] if cached else []  # an out-of-date list is better than nothing


def complete_migratable_groups(ctx: typer.Context, incomplete: str) -> list[tuple[str, str]]:
    """Names of the groups `group migrate` can act on (active Synced Groups), for `--group`.

    A name shared by several of them cannot be told apart by name (migrate refuses it), so those are offered by ID.
    Needs a session, so it only completes once `-s <session>` has been typed.
    """
    try:
        session = ctx.find_root().params.get("session")
        if not session:
            return []
        groups = [g for g in _groups_for(session) if g.get("type") == "SYNCED" and g.get("isActive")]
        names = [g["name"] for g in groups]
        typed = incomplete.lstrip("\"'").lower()
        offers: list[tuple[str, str]] = []
        for g in groups:
            value, help_text = (g["id"], g["name"]) if names.count(g["name"]) > 1 else (g["name"], g["id"])
            if value.lower().startswith(typed) or g["id"].lower().startswith(typed):
                offers.append((value, help_text))
        return sorted(offers, key=lambda offer: offer[0].lower())
    except Exception:
        return []
