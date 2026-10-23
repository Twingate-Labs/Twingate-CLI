"""Shell completion runs on every TAB press: it must be right, fast, private, and silent when anything goes wrong."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tgcli import completion as c
from tgcli.client.session import SessionManager

NOW = 1_000_000.0


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(c, "_IS_WINDOWS", False)
    return tmp_path / "cache" / "tgcli"


def g(name, gid=None, type="SYNCED", active=True):
    return {"id": gid or f"id-{name}", "name": name, "type": type, "isActive": active}


def ctx_with(session):
    return SimpleNamespace(find_root=lambda: SimpleNamespace(params={"session": session}))


class TestSessions:
    def test_offers_saved_sessions_sorted(self, mock_keyring):
        for name in ("zeta", "alpha", "beta"):
            SessionManager.store(name, "acme", "tok")
        assert c.complete_session("") == ["alpha", "beta", "zeta"]

    def test_filters_by_prefix(self, mock_keyring):
        for name in ("prod", "prod-eu", "staging"):
            SessionManager.store(name, "acme", "tok")
        assert c.complete_session("prod") == ["prod", "prod-eu"]
        assert c.complete_session("x") == []

    def test_prefix_is_case_sensitive_like_the_names_themselves(self, mock_keyring):
        SessionManager.store("Prod", "acme", "tok")
        assert c.complete_session("p") == []

    def test_a_keychain_failure_offers_nothing_instead_of_raising(self):
        with patch.object(SessionManager, "list_sessions", side_effect=RuntimeError("keychain locked")):
            assert c.complete_session("") == []


class TestCachePaths:
    def test_follows_xdg_cache_home_on_unix(self, isolated_cache):
        assert c._cache_dir() == isolated_cache

    def test_falls_back_to_dot_cache_in_the_home_directory(self, monkeypatch):
        monkeypatch.delenv("XDG_CACHE_HOME")
        assert c._cache_dir() == Path.home() / ".cache" / "tgcli"

    def test_uses_local_app_data_on_windows(self, monkeypatch, tmp_path):
        monkeypatch.setattr(c, "_IS_WINDOWS", True)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
        assert c._cache_dir() == tmp_path / "Local" / "tgcli"

    def test_the_file_depends_on_session_and_tenant_but_not_on_anything_else(self):
        a = c._cache_file("prod", "https://a.twingate.com/api/graphql/")
        assert a == c._cache_file("prod", "https://a.twingate.com/api/graphql/")
        assert a != c._cache_file("staging", "https://a.twingate.com/api/graphql/")
        assert a != c._cache_file("prod", "https://b.twingate.com/api/graphql/")
        assert "prod" not in a.name and "twingate" not in a.name  # no session or tenant name on disk in the file name


class TestCacheFile:
    def test_round_trip(self, isolated_cache):
        path = isolated_cache / "groups-x.json"
        c._write_cache(path, [g("Eng")])
        groups, fetched = c._read_cache(path)
        assert groups == [g("Eng")] and abs(fetched - time.time()) < 5

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
    def test_the_cache_is_private_to_the_user(self, isolated_cache):
        old = os.umask(0o000)
        try:
            c._write_cache(isolated_cache / "groups-x.json", [g("Eng")])
        finally:
            os.umask(old)
        assert stat.S_IMODE(isolated_cache.stat().st_mode) == 0o700
        assert stat.S_IMODE((isolated_cache / "groups-x.json").stat().st_mode) == 0o600

    @pytest.mark.parametrize("content", ["", "{not json", "[]", '{"fetched": 1}', '{"groups": []}', '{"groups": 5, "fetched": 1}'])
    def test_a_missing_corrupt_or_odd_file_reads_as_nothing(self, isolated_cache, content):
        path = isolated_cache / "groups-x.json"
        path.parent.mkdir(parents=True)
        path.write_text(content)
        assert c._read_cache(path) is None

    def test_a_file_that_does_not_exist_reads_as_nothing(self, isolated_cache):
        assert c._read_cache(isolated_cache / "nope.json") is None

    def test_failing_to_write_is_silent(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("a file where the directory should be")
        c._write_cache(blocker / "sub" / "groups.json", [g("Eng")])  # must not raise

    def test_no_temp_file_is_left_behind(self, isolated_cache):
        c._write_cache(isolated_cache / "groups-x.json", [g("Eng")])
        assert [p.name for p in isolated_cache.iterdir()] == ["groups-x.json"]


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


def page(nodes, more=False, end=None):
    return FakeResponse({"data": {"groups": {"pageInfo": {"hasNextPage": more, "endCursor": end}, "edges": [{"node": n} for n in nodes]}}})


class TestFetch:
    def test_follows_every_page(self):
        pages = [page([g("a")], True, "c1"), page([g("b")], True, "c2"), page([g("c")])]
        with patch.object(c.requests, "post", side_effect=pages) as post:
            result = c._fetch_groups("https://x/api", {"X-API-KEY": "k"}, 3.0)
        assert [x["name"] for x in result] == ["a", "b", "c"]
        assert [call.kwargs["json"]["variables"]["cursor"] for call in post.call_args_list] == [None, "c1", "c2"]
        assert all(call.args == ("https://x/api",) and call.kwargs["headers"] == {"X-API-KEY": "k"} for call in post.call_args_list)

    def test_each_request_is_limited_to_the_remaining_budget(self):
        with patch.object(c.requests, "post", return_value=page([g("a")])) as post:
            c._fetch_groups("https://x/api", {}, 2.5)
        assert 0 < post.call_args.kwargs["timeout"] <= 2.5

    def test_gives_up_when_the_budget_runs_out_midway(self):
        clock = iter([0.0, 0.1, 5.0, 5.0, 5.0])
        with patch.object(c.time, "monotonic", side_effect=lambda: next(clock)), \
                patch.object(c.requests, "post", return_value=page([g("a")], True, "c1")) as post:
            assert c._fetch_groups("https://x/api", {}, 3.0) is None
        assert post.call_count == 1

    @pytest.mark.parametrize("response", [FakeResponse({}, 429), FakeResponse({}, 500), FakeResponse({"errors": [{"message": "x"}]}), FakeResponse({"data": {}}, 401)])
    def test_an_error_reply_means_nothing_to_offer_and_never_sleeps(self, response):
        with patch.object(c.requests, "post", return_value=response), patch("time.sleep") as sleep:
            assert c._fetch_groups("https://x/api", {}, 3.0) is None
        sleep.assert_not_called()


@pytest.fixture
def fake_client():
    with patch("tgcli.client.client.TwingateClient") as MockClient:
        inst = MockClient.return_value
        inst.url = "https://acme.twingate.com/api/graphql/"
        inst._headers.return_value = {"X-API-KEY": "k"}
        yield inst


class TestGroupsFor:
    def test_fetches_once_then_serves_from_the_cache(self, fake_client):
        with patch.object(c, "_fetch_groups", return_value=[g("Eng")]) as fetch:
            assert c._groups_for("prod") == [g("Eng")]
            assert c._groups_for("prod") == [g("Eng")]
        assert fetch.call_count == 1

    def test_an_expired_cache_is_refreshed_and_rewritten(self, fake_client):
        with patch.object(c, "_fetch_groups", return_value=[g("Old")]):
            c._groups_for("prod")
        path = c._cache_file("prod", fake_client.url)
        data = json.loads(path.read_text())
        data["fetched"] = time.time() - c.CACHE_TTL_SECONDS - 1
        path.write_text(json.dumps(data))
        with patch.object(c, "_fetch_groups", return_value=[g("New")]) as fetch:
            assert c._groups_for("prod") == [g("New")]
        fetch.assert_called_once()
        assert json.loads(path.read_text())["groups"] == [g("New")]

    @pytest.mark.parametrize("failure", [dict(return_value=None), dict(side_effect=ConnectionError("down")), dict(side_effect=ValueError("bad json"))])
    def test_when_the_fetch_fails_an_old_list_is_better_than_nothing(self, fake_client, failure):
        c._write_cache(c._cache_file("prod", fake_client.url), [g("Stale")])
        path = c._cache_file("prod", fake_client.url)
        data = json.loads(path.read_text()); data["fetched"] = 0; path.write_text(json.dumps(data))
        with patch.object(c, "_fetch_groups", **failure):
            assert c._groups_for("prod") == [g("Stale")]

    @pytest.mark.parametrize("failure", [dict(return_value=None), dict(side_effect=ConnectionError("down"))])
    def test_when_the_fetch_fails_and_there_is_no_cache_there_is_nothing(self, fake_client, failure):
        with patch.object(c, "_fetch_groups", **failure):
            assert c._groups_for("prod") == []

    def test_a_failed_fetch_never_overwrites_the_cache(self, fake_client):
        path = c._cache_file("prod", fake_client.url)
        c._write_cache(path, [g("Good")])
        data = json.loads(path.read_text()); data["fetched"] = 0; path.write_text(json.dumps(data))
        with patch.object(c, "_fetch_groups", return_value=None):
            c._groups_for("prod")
        assert json.loads(path.read_text())["groups"] == [g("Good")]

    def test_two_sessions_do_not_share_a_cache(self, fake_client):
        with patch.object(c, "_fetch_groups", side_effect=[[g("A")], [g("B")]]):
            assert c._groups_for("one") == [g("A")]
            assert c._groups_for("two") == [g("B")]


class TestMigratableGroups:
    def offered(self, groups, incomplete="", session="prod"):
        with patch.object(c, "_groups_for", return_value=groups):
            return c.complete_migratable_groups(ctx_with(session), incomplete)

    def test_only_active_synced_groups_are_offered(self):
        groups = [g("Eng"), g("Manual", type="MANUAL"), g("Retired", active=False), g("System", type="SYSTEM")]
        assert [v for v, _ in self.offered(groups)] == ["Eng"]

    def test_each_name_comes_with_its_id_as_help(self):
        assert self.offered([g("Eng", "R3JvdXA6MQ==")]) == [("Eng", "R3JvdXA6MQ==")]

    def test_prefix_matching_ignores_case(self):
        groups = [g("Engineering"), g("Ops"), g("energy")]
        assert [v for v, _ in self.offered(groups, "en")] == ["energy", "Engineering"]

    def test_a_group_can_also_be_found_by_the_start_of_its_id(self):
        assert self.offered([g("Eng", "R3JvdXA6MQ=="), g("Ops", "T3Bz")], "R3Jv") == [("Eng", "R3JvdXA6MQ==")]

    def test_a_quote_the_user_already_typed_is_ignored(self):
        groups = [g("Eng")]
        assert self.offered(groups, '"En') == [("Eng", "id-Eng")] and self.offered(groups, "'En") == [("Eng", "id-Eng")]

    def test_a_name_shared_by_several_groups_is_offered_by_id_because_migrate_refuses_the_name(self):
        groups = [g("Eng", "id1"), g("Eng", "id2"), g("Ops", "id3")]
        assert self.offered(groups) == [("id1", "Eng"), ("id2", "Eng"), ("Ops", "id3")]

    def test_results_are_sorted(self):
        assert [v for v, _ in self.offered([g("b"), g("A"), g("c")])] == ["A", "b", "c"]

    def test_nothing_is_offered_before_a_session_is_chosen(self):
        with patch.object(c, "_groups_for") as groups_for:
            assert c.complete_migratable_groups(ctx_with(""), "") == []
            assert c.complete_migratable_groups(ctx_with(None), "") == []
        groups_for.assert_not_called()

    def test_any_failure_offers_nothing_instead_of_raising(self):
        with patch.object(c, "_groups_for", side_effect=RuntimeError("boom")):
            assert c.complete_migratable_groups(ctx_with("prod"), "") == []

    def test_a_context_without_a_root_offers_nothing(self):
        assert c.complete_migratable_groups(SimpleNamespace(), "") == []


class TestWiring:
    """Drive Typer's real completion protocol in-process, so the options really are hooked up."""

    def complete(self, words, capsys, monkeypatch):
        import tgcli.main

        monkeypatch.setenv("_TGCLI_COMPLETE", "complete_bash")
        monkeypatch.setenv("COMP_WORDS", words)
        monkeypatch.setenv("COMP_CWORD", str(len(words.split(" ")) - 1))
        with pytest.raises(SystemExit) as exit_info:
            tgcli.main.app(prog_name="tgcli")
        assert exit_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        return captured.out.split()

    def test_the_session_option_completes_saved_sessions(self, mock_keyring, capsys, monkeypatch):
        for name in ("alpha", "beta"):
            SessionManager.store(name, "acme", "tok")
        assert self.complete("tgcli -s ", capsys, monkeypatch) == ["alpha", "beta"]
        assert self.complete("tgcli --session b", capsys, monkeypatch) == ["beta"]

    def test_migrate_group_completes_names_for_the_session_typed_earlier(self, mock_keyring, isolated_cache, capsys, monkeypatch):
        seen = []
        with patch.object(c, "_groups_for", side_effect=lambda s: seen.append(s) or [g("Eng"), g("Manual", type="MANUAL"), g("Ops")]):
            assert self.complete("tgcli -s prod group migrate --group ", capsys, monkeypatch) == ["Eng", "Ops"]
            assert self.complete("tgcli -s prod group migrate -g O", capsys, monkeypatch) == ["Ops"]
        assert seen == ["prod", "prod"]

    def test_migrate_group_offers_nothing_without_a_session(self, mock_keyring, capsys, monkeypatch):
        assert self.complete("tgcli group migrate --group ", capsys, monkeypatch) == []

    def test_ordinary_command_completion_still_works(self, mock_keyring, capsys, monkeypatch):
        assert "group" in self.complete("tgcli gr", capsys, monkeypatch)
