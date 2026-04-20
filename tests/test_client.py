"""Tests for TwingateClient (HTTP + retry + pagination)."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
import responses as resp_lib

from tgcli.client.client import THROTTLE_DEFAULT_WAIT, THROTTLE_MAX_RETRIES, TwingateClient
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError, TwingateThrottleError
from tgcli.client.session import SessionManager

API_URL = "https://acme.twingate.com/api/graphql/"
SESSION = "TestSession"
TOKEN = "tok-test-123"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    """Pre-store a session so TwingateClient can resolve credentials."""
    SessionManager.store(SESSION, "acme", TOKEN)
    return SESSION


@pytest.fixture
def client() -> TwingateClient:
    return TwingateClient(SESSION)


class TestCredentialResolution:
    def test_lazy_token_resolution(self, client):
        assert client._token is None
        _ = client.token
        assert client._token == TOKEN

    def test_lazy_url_resolution(self, client):
        assert client._url is None
        _ = client.url
        assert client._url == API_URL

    def test_missing_session_raises_auth_error(self, mock_keyring):
        bad_client = TwingateClient("nonexistent")
        with pytest.raises(TwingateAuthError):
            _ = bad_client.token


class TestExecute:
    @resp_lib.activate
    def test_successful_query(self, client):
        resp_lib.add(
            resp_lib.POST,
            API_URL,
            json={"data": {"resources": {"edges": [], "pageInfo": {"hasNextPage": False}}}},
            status=200,
        )
        result = client.execute("query { resources { edges { node { id } } } }")
        assert "data" in result

    @resp_lib.activate
    def test_http_error_raises_api_error(self, client):
        resp_lib.add(resp_lib.POST, API_URL, json={"message": "Unauthorized"}, status=401)
        with pytest.raises(TwingateAPIError, match="HTTP 401"):
            client.execute("query { resources { edges { node { id } } } }")

    @resp_lib.activate
    def test_graphql_errors_raises_api_error(self, client):
        resp_lib.add(
            resp_lib.POST,
            API_URL,
            json={"data": None, "errors": [{"message": "Resource not found"}]},
            status=200,
        )
        with pytest.raises(TwingateAPIError, match="Resource not found"):
            client.execute("query { resource(id: \"bad\") { id } }")

    @resp_lib.activate
    def test_html_response_raises_api_error(self, client):
        resp_lib.add(
            resp_lib.POST,
            API_URL,
            body="<!doctype html><html><body>Login</body></html>",
            status=200,
            content_type="text/html",
        )
        with pytest.raises(TwingateAPIError, match="HTML response"):
            client.execute("query { resource(id: \"x\") { id } }")

    @resp_lib.activate
    def test_sets_api_key_header(self, client):
        resp_lib.add(
            resp_lib.POST,
            API_URL,
            json={"data": {}},
            status=200,
        )
        client.execute("query { resources { edges { node { id } } } }")
        assert resp_lib.calls[0].request.headers["X-API-KEY"] == TOKEN


class TestPaginate:
    @resp_lib.activate
    def test_single_page(self, client):
        resp_lib.add(
            resp_lib.POST,
            API_URL,
            json={
                "data": {
                    "resources": {
                        "edges": [{"node": {"id": "r1"}}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            },
            status=200,
        )
        pages = client.paginate("query Q($cursor:String!){resources(after:$cursor){edges{node{id}}pageInfo{hasNextPage endCursor}}}", lambda c: {"cursor": c}, "resources")
        assert len(pages) == 1
        assert pages[0][0]["node"]["id"] == "r1"

    @resp_lib.activate
    def test_two_pages(self, client):
        # First page has hasNextPage=True
        resp_lib.add(
            resp_lib.POST,
            API_URL,
            json={
                "data": {
                    "items": {
                        "edges": [{"node": {"id": "r1"}}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-2"},
                    }
                }
            },
            status=200,
        )
        # Second page
        resp_lib.add(
            resp_lib.POST,
            API_URL,
            json={
                "data": {
                    "items": {
                        "edges": [{"node": {"id": "r2"}}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            },
            status=200,
        )
        pages = client.paginate("query Q($cursor:String!){items(after:$cursor){edges{node{id}}pageInfo{hasNextPage endCursor}}}", lambda c: {"cursor": c}, "items")
        assert len(pages) == 2
        assert pages[0][0]["node"]["id"] == "r1"
        assert pages[1][0]["node"]["id"] == "r2"


class TestCheckHttpResponse:
    def test_ok_response_passes(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"data":{}}'
        TwingateClient._check_http_response(mock_resp)  # should not raise

    def test_500_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with pytest.raises(TwingateAPIError, match="HTTP 500"):
            TwingateClient._check_http_response(mock_resp)


class TestCheckGraphqlErrors:
    def test_no_errors_key_passes(self):
        TwingateClient._check_graphql_errors({"data": {}})  # should not raise

    def test_empty_errors_list_passes(self):
        TwingateClient._check_graphql_errors({"data": {}, "errors": []})  # should not raise

    def test_errors_raises(self):
        with pytest.raises(TwingateAPIError, match="Something went wrong"):
            TwingateClient._check_graphql_errors(
                {"data": None, "errors": [{"message": "Something went wrong"}]}
            )


# ---------------------------------------------------------------------------
# Throttle / rate-limit handling
# ---------------------------------------------------------------------------

class TestCheckHttpResponseThrottle:
    """Unit tests for the 429-specific branch of _check_http_response."""

    def _make_response(self, status: int, headers: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.headers = headers
        mock_resp.text = ""
        return mock_resp

    def test_429_raises_throttle_error(self):
        resp = self._make_response(429, {"Retry-After": "30"})
        with pytest.raises(TwingateThrottleError) as exc_info:
            TwingateClient._check_http_response(resp)
        assert exc_info.value.retry_after == 30
        assert exc_info.value.status_code == 429

    def test_429_uses_default_wait_when_header_absent(self):
        resp = self._make_response(429, {})
        with pytest.raises(TwingateThrottleError) as exc_info:
            TwingateClient._check_http_response(resp)
        assert exc_info.value.retry_after == THROTTLE_DEFAULT_WAIT

    def test_429_uses_default_wait_when_header_not_an_int(self):
        resp = self._make_response(429, {"Retry-After": "Wed, 26 Feb 2026 12:00:00 GMT"})
        with pytest.raises(TwingateThrottleError) as exc_info:
            TwingateClient._check_http_response(resp)
        assert exc_info.value.retry_after == THROTTLE_DEFAULT_WAIT

    def test_non_429_still_raises_generic_api_error(self):
        resp = self._make_response(503, {})
        resp.text = "Service Unavailable"
        with pytest.raises(TwingateAPIError) as exc_info:
            TwingateClient._check_http_response(resp)
        assert not isinstance(exc_info.value, TwingateThrottleError)


class TestThrottleRetry:
    """Integration-style tests for execute()'s throttle-retry loop."""

    @resp_lib.activate
    def test_single_throttle_then_success_retries(self, client):
        """One 429 → warning printed → sleep → success on second attempt."""
        resp_lib.add(resp_lib.POST, API_URL, json={}, status=429,
                     headers={"Retry-After": "5"})
        resp_lib.add(resp_lib.POST, API_URL, json={"data": {"ok": True}}, status=200)

        with patch("tgcli.client.client.time.sleep") as mock_sleep:
            result = client.execute("query { ok }")

        mock_sleep.assert_called_once_with(5)
        assert result["data"]["ok"] is True

    @resp_lib.activate
    def test_multiple_throttles_then_success(self, client):
        """Two 429s → two sleeps → success on third attempt."""
        resp_lib.add(resp_lib.POST, API_URL, json={}, status=429,
                     headers={"Retry-After": "2"})
        resp_lib.add(resp_lib.POST, API_URL, json={}, status=429,
                     headers={"Retry-After": "4"})
        resp_lib.add(resp_lib.POST, API_URL, json={"data": {"ok": True}}, status=200)

        with patch("tgcli.client.client.time.sleep") as mock_sleep:
            result = client.execute("query { ok }")

        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list == [call(2), call(4)]
        assert result["data"]["ok"] is True

    @resp_lib.activate
    def test_exhausted_retries_raises_api_error(self, client):
        """THROTTLE_MAX_RETRIES+1 consecutive 429s → TwingateAPIError."""
        for _ in range(THROTTLE_MAX_RETRIES + 1):
            resp_lib.add(resp_lib.POST, API_URL, json={}, status=429,
                         headers={"Retry-After": "1"})

        with patch("tgcli.client.client.time.sleep"):
            with pytest.raises(TwingateAPIError, match="(?i)rate limit exceeded"):
                client.execute("query { ok }")

    @resp_lib.activate
    def test_exhausted_retries_sleep_count(self, client):
        """Exactly THROTTLE_MAX_RETRIES sleeps happen before giving up."""
        for _ in range(THROTTLE_MAX_RETRIES + 1):
            resp_lib.add(resp_lib.POST, API_URL, json={}, status=429,
                         headers={"Retry-After": "1"})

        with patch("tgcli.client.client.time.sleep") as mock_sleep:
            with pytest.raises(TwingateAPIError):
                client.execute("query { ok }")

        assert mock_sleep.call_count == THROTTLE_MAX_RETRIES

    @resp_lib.activate
    def test_throttle_warning_printed_to_stderr(self, client, capsys):
        """Warning message appears on stderr with wait-time and attempt info."""
        resp_lib.add(resp_lib.POST, API_URL, json={}, status=429,
                     headers={"Retry-After": "42"})
        resp_lib.add(resp_lib.POST, API_URL, json={"data": {}}, status=200)

        with patch("tgcli.client.client.time.sleep"):
            client.execute("query { ok }")

        captured = capsys.readouterr()
        assert "Rate limited" in captured.err
        assert "42s" in captured.err
        assert "1/" in captured.err  # "attempt 1/N"

    @resp_lib.activate
    def test_throttle_mid_pagination_retries_transparently(self, client):
        """A 429 on page 2 of a paginated query retries and continues."""
        # Page 1 — OK
        resp_lib.add(
            resp_lib.POST, API_URL,
            json={"data": {"items": {
                "edges": [{"node": {"id": "r1"}}],
                "pageInfo": {"hasNextPage": True, "endCursor": "cur2"},
            }}},
            status=200,
        )
        # Page 2 — throttled first, then OK
        resp_lib.add(resp_lib.POST, API_URL, json={}, status=429,
                     headers={"Retry-After": "1"})
        resp_lib.add(
            resp_lib.POST, API_URL,
            json={"data": {"items": {
                "edges": [{"node": {"id": "r2"}}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }}},
            status=200,
        )

        with patch("tgcli.client.client.time.sleep"):
            pages = client.paginate(
                "query Q($cursor:String!){items(after:$cursor)"
                "{edges{node{id}}pageInfo{hasNextPage endCursor}}}",
                lambda c: {"cursor": c},
                "items",
            )

        assert len(pages) == 2
        assert pages[0][0]["node"]["id"] == "r1"
        assert pages[1][0]["node"]["id"] == "r2"
