"""Twingate GraphQL API client.

Replaces StdAPIUtils.generic_api_call_handler with a clean class that adds:
  - Lazy session credential resolution
  - Exponential-backoff retry on connection errors (via tenacity)
  - Automatic retry with user-visible warning on HTTP 429 throttle responses
  - Cursor-based pagination helper
  - Proper exception hierarchy instead of exit() calls
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Callable

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tgcli.client.exceptions import (
    TwingateAPIError,
    TwingateAuthError,
    TwingateThrottleError,
)
from tgcli.client.session import SessionManager

USER_AGENT = "TwingatePythonCLI/2.0.0"

#: Number of *retries* after the first throttled attempt (total calls = +1).
THROTTLE_MAX_RETRIES: int = 3

#: Fallback wait (seconds) when the API omits the ``Retry-After`` header.
THROTTLE_DEFAULT_WAIT: int = 60

logger = logging.getLogger(__name__)


class TwingateClient:
    """HTTP client for the Twingate Admin GraphQL API."""

    def __init__(self, session: str, token: str | None = None, url: str | None = None) -> None:
        self.session = session
        self._token: str | None = token
        self._url: str | None = url
        self._http = requests.Session()

    # ------------------------------------------------------------------
    # Credential resolution (lazy — avoids keyring call if not needed)
    # ------------------------------------------------------------------

    @property
    def token(self) -> str:
        if self._token is None:
            self._token = SessionManager.get_token(self.session)
        return self._token

    @property
    def url(self) -> str:
        if self._url is None:
            self._url = SessionManager.get_url(self.session)
        return self._url

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-KEY": self.token,
            "User-agent": USER_AGENT,
        }

    # ------------------------------------------------------------------
    # Public single-shot execute (no throttle retry)
    # ------------------------------------------------------------------

    def execute_once(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single GraphQL call without throttle retry.

        Useful when the caller manages its own retry/progress logic.
        """
        return self._execute_once(query, variables)

    # ------------------------------------------------------------------
    # Core execute — throttle retry wrapper around the single-shot call
    # ------------------------------------------------------------------

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query or mutation, with automatic 429 retry.

        When the API returns HTTP 429 (rate limited), a warning is printed to
        *stderr* and the request is retried after the ``Retry-After`` delay.
        After :data:`THROTTLE_MAX_RETRIES` retries the call fails with
        :class:`~tgcli.client.exceptions.TwingateAPIError`.

        Args:
            query:     The GraphQL query/mutation string.
            variables: Optional dict of GraphQL variables.

        Returns:
            The parsed JSON response dict (full response, including 'data' key).

        Raises:
            TwingateAuthError:    If the session credentials are missing.
            TwingateThrottleError: Propagated if still throttled after all retries.
            TwingateAPIError:     On HTTP errors, HTML redirects, or GraphQL errors.
        """
        for attempt in range(THROTTLE_MAX_RETRIES + 1):
            try:
                return self._execute_once(query, variables)
            except TwingateThrottleError as exc:
                if attempt >= THROTTLE_MAX_RETRIES:
                    raise TwingateAPIError(
                        f"Rate limit exceeded after {THROTTLE_MAX_RETRIES} "
                        "retries. Please wait and try again later.",
                        status_code=429,
                    ) from exc
                wait = exc.retry_after
                print(
                    f"⚠  Rate limited by Twingate API. "
                    f"Waiting {wait}s before retrying "
                    f"(attempt {attempt + 1}/{THROTTLE_MAX_RETRIES})...",
                    file=sys.stderr,
                )
                time.sleep(wait)

        # Unreachable — the loop always returns or raises above.
        raise RuntimeError("Throttle retry loop exited unexpectedly")  # pragma: no cover

    # ------------------------------------------------------------------
    # Single HTTP round-trip (tenacity retries on connection errors only)
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.ConnectionError),
        reraise=True,
    )
    def _execute_once(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Single HTTP POST to the GraphQL endpoint (no throttle retry here)."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        logger.debug("POST %s  variables=%s", self.url, variables)

        try:
            response = self._http.post(
                self.url,
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
        except requests.exceptions.Timeout as exc:
            raise TwingateAPIError("Request timed out after 30 s.") from exc

        logger.debug("Response %s: %.500s", response.status_code, response.text)

        self._check_http_response(response)
        result: dict[str, Any] = response.json()
        self._check_graphql_errors(result)
        return result

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    def paginate(
        self,
        query: str,
        variables_factory: Callable[[str], dict[str, Any]],
        data_key: str,
    ) -> list[list[dict[str, Any]]]:
        """Execute a cursor-paginated list query and return all pages.

        Throttle handling is automatic — if the API rate-limits mid-pagination
        the underlying :meth:`execute` call will retry transparently.

        Args:
            query:             GraphQL query string (must accept $cursor: String!).
            variables_factory: Callable(cursor) → variables dict.
            data_key:          Top-level key inside 'data' (e.g. "resources").

        Returns:
            List of edge-lists, one per page.
            e.g. [[edge1, edge2], [edge3]] for a 2-page result.
        """
        all_pages: list[list[dict[str, Any]]] = []
        cursor = "0"
        has_next = True

        while has_next:
            variables = variables_factory(cursor)
            result = self.execute(query, variables)
            page_data = result["data"][data_key]
            all_pages.append(page_data["edges"])
            page_info = page_data["pageInfo"]
            has_next = page_info.get("hasNextPage", False)
            if has_next:
                cursor = page_info["endCursor"]

        return all_pages

    def paginate_parallel(
        self,
        query: str,
        data_key: str,
        reads_per_min: int = 60,
        max_concurrent: int = 10,
        page_size: int = 50,
        on_progress: Callable[..., None] | None = None,
        on_throttle: Callable[..., None] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages concurrently using offset-based cursors.

        Twingate's Relay cursors are ``base64("arrayconnection:N")`` where
        N is the zero-based index of the last item on the page. This method
        fetches page 1 to discover ``totalCount``, calculates all remaining
        cursors, and fetches them in concurrent batches bounded by
        *max_concurrent* and *reads_per_min*.

        Args:
            query:          GraphQL query string (must accept ``$cursor: String!``).
            data_key:       Top-level key inside ``data`` (e.g. ``"resources"``).
            reads_per_min:  Max API reads per 60-second window.
            max_concurrent: Max parallel requests in a single batch.
            page_size:      Items per page (API max is typically 50).
            on_progress:    Optional callback(items_so_far, total, batch_num, batch_size, total_pages).
            on_throttle:    Optional callback(failed_count, retry_after, items_so_far, total).

        Returns:
            Flat list of node dicts (deduplicated by ``id``).
        """
        import base64
        import concurrent.futures
        import time as _time

        def _make_cursor(last_index: int) -> str:
            return base64.b64encode(f"arrayconnection:{last_index}".encode()).decode()

        def _fetch(cursor: str) -> dict[str, Any] | None:
            for attempt in range(THROTTLE_MAX_RETRIES + 1):
                try:
                    return self._execute_once(query, {"cursor": cursor})
                except TwingateThrottleError as exc:
                    if attempt >= THROTTLE_MAX_RETRIES:
                        return None
                    if on_throttle:
                        on_throttle(1, exc.retry_after, len(all_nodes), total_count if 'total_count' in dir() else 0)
                    _time.sleep(exc.retry_after)
            return None

        seen_ids: set[str] = set()
        all_nodes: list[dict[str, Any]] = []

        def _collect(result: dict[str, Any]) -> None:
            for edge in result["data"][data_key].get("edges", []):
                node = edge["node"]
                nid = node.get("id")
                if nid and nid in seen_ids:
                    continue
                if nid:
                    seen_ids.add(nid)
                all_nodes.append(node)

        # Phase 1: first page
        first = _fetch("0")
        if first is None:
            raise TwingateAPIError("Failed to fetch first page.")
        _collect(first)
        total_count = first["data"][data_key].get("totalCount") or len(all_nodes)

        # Phase 2: remaining pages in parallel batches
        cursors = [_make_cursor(i) for i in range(page_size - 1, total_count, page_size)]
        total_pages = len(cursors) + 1
        total_batches = 1 + (len(cursors) + max_concurrent - 1) // max_concurrent if cursors else 1
        budget = reads_per_min - 1
        batch_num = 1

        if on_progress:
            on_progress(len(all_nodes), total_count, 1, max_concurrent, total_batches)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            while cursors:
                batch_size = min(len(cursors), max_concurrent, max(1, budget))
                batch = cursors[:batch_size]
                cursors = cursors[batch_size:]

                futures = {pool.submit(_fetch, cur): cur for cur in batch}
                failed: list[str] = []
                for fut in concurrent.futures.as_completed(futures):
                    result = fut.result()
                    if result is None:
                        failed.append(futures[fut])
                    else:
                        _collect(result)

                if failed:
                    if on_throttle:
                        on_throttle(len(failed), 30, len(all_nodes), total_count)
                    _time.sleep(30)
                    for cur in failed:
                        retry = _fetch(cur)
                        if retry:
                            _collect(retry)
                        budget -= 1

                batch_num += 1
                budget -= batch_size
                if on_progress:
                    on_progress(len(all_nodes), total_count, batch_num, len(batch), total_batches)

                if budget <= 0 and cursors:
                    _time.sleep(60)
                    budget = reads_per_min

        return all_nodes

    # ------------------------------------------------------------------
    # Internal validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_http_response(response: requests.Response) -> None:
        # 429 is checked first so it raises TwingateThrottleError, not a
        # generic TwingateAPIError, enabling the throttle retry logic above.
        if response.status_code == 429:
            retry_after_str = response.headers.get(
                "Retry-After", str(THROTTLE_DEFAULT_WAIT)
            )
            try:
                retry_after = int(retry_after_str)
            except (ValueError, TypeError):
                retry_after = THROTTLE_DEFAULT_WAIT
            raise TwingateThrottleError(retry_after)

        if response.status_code >= 300:
            hint = (
                " Check your tenant name and try logging in again."
                if response.status_code in (401, 403, 500)
                else ""
            )
            raise TwingateAPIError(
                f"HTTP {response.status_code}: {response.text[:300]}.{hint}",
                status_code=response.status_code,
            )
        # Detect HTML login-redirect (misconfigured tenant)
        text = response.text.strip()
        if text.startswith("<!doctype html") or text.startswith("<html"):
            raise TwingateAPIError(
                "Received an HTML response — check your tenant name and try logging in again.",
                status_code=response.status_code,
            )

    @staticmethod
    def _check_graphql_errors(result: dict[str, Any]) -> None:
        errors = result.get("errors")
        if errors:
            message = errors[0].get("message", "Unknown GraphQL error")
            raise TwingateAPIError(f"GraphQL error: {message}")
