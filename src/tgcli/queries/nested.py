"""Builders for nested GraphQL lists that must be followed past the API's 50-item page limit."""

from __future__ import annotations


def connection(field: str, edge: str) -> str:
    """A nested list as the first page sees it: with the count and cursor needed to spot and finish truncation."""
    return f"{field} {{ totalCount pageInfo {{ hasNextPage endCursor }} edges {{ {edge} }} }}"


def continuation(parent: str, field: str, edge: str, on: tuple[str, ...] = ()) -> str:
    """The same nested list fetched on its own, to read the pages after the first.

    ``on`` lists the concrete types to spread over when ``field`` only exists on implementations of an interface.
    """
    inner = f"{field}(after: $cursor) {{ pageInfo {{ hasNextPage endCursor }} edges {{ {edge} }} }}"
    if on:
        inner = " ".join(f"... on {t} {{ {inner} }}" for t in on)
    return f"query($id: ID!, $cursor: String) {{ {parent}(id: $id) {{ {inner} }} }}"
