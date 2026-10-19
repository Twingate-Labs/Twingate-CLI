"""group migrate: copy each active Synced Group into a Manual Group (dry run by default)."""

from __future__ import annotations

import csv
import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
POLICY = {"id": "pol-src", "name": "Strict"}


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def group(gid, name, gtype="SYNCED", active=True, policy=POLICY):
    return {"id": gid, "name": name, "type": gtype, "isActive": active, "securityPolicy": policy}


class Api:
    """The parts of the Twingate API migrate uses, returning real response shapes: {"data": {...}}.

    Only fields the query actually selects are returned, so a query that forgets one is noticed.
    """

    def __init__(self, groups, users=None, resources=None, page=2):
        self.groups, self.users, self.resources, self.page = groups, users or {}, resources or {}, page
        self.calls: list[tuple[str, dict]] = []
        self.created: list[dict] = []
        self.user_chunks: list[tuple[str, list]] = []
        self.resource_chunks: list[tuple[str, list]] = []
        self.create_error = self.users_error = self.resources_error = None
        self.raise_on: tuple[str, Exception] | None = None
        self.list_error: Exception | None = None

    def paginate(self, query, make_vars, data_key):
        assert data_key == "groups"
        if self.list_error:
            raise self.list_error
        keep = {k for k in ("id", "name", "type", "isActive", "securityPolicy") if k in query}
        return [[{"node": {k: v for k, v in g.items() if k in keep}} for g in self.groups]]

    def _connection(self, ids, field, after):
        start = 0 if after is None else int(after[1:])
        more = start + self.page < len(ids)
        return {field: {
            "pageInfo": {"hasNextPage": more, "endCursor": f"c{start + self.page}" if more else None},
            "edges": [{"node": {"id": i}} for i in ids[start : start + self.page]],
        }}

    def execute(self, query, variables=None):
        variables = variables or {}
        name = re.search(r"(?:query|mutation) (\w+)", query).group(1)
        self.calls.append((name, variables))
        if self.raise_on and self.raise_on[0] == name:
            raise self.raise_on[1]
        if name == "groupUsers":
            return {"data": {"group": self._connection(self.users.get(variables["id"], []), "users", variables.get("after"))}}
        if name == "groupResources":
            return {"data": {"group": self._connection(self.resources.get(variables["id"], []), "resources", variables.get("after"))}}
        if name == "createGroup":
            if self.create_error:
                return {"data": {"groupCreate": {"ok": False, "error": self.create_error, "entity": None}}}
            self.created.append(variables)
            return {"data": {"groupCreate": {"ok": True, "error": None, "entity": {"id": f"new-{len(self.created)}"}}}}
        if name in ("addUsersToGroup", "addResToGroup"):
            error = self.users_error if name == "addUsersToGroup" else self.resources_error
            if error:
                return {"data": {"groupUpdate": {"ok": False, "error": error, "entity": None}}}
            (self.user_chunks if name == "addUsersToGroup" else self.resource_chunks).append(
                (variables["groupID"], variables["userIDS" if name == "addUsersToGroup" else "resourceIDS"])
            )
            return {"data": {"groupUpdate": {"ok": True, "error": None, "entity": {"id": variables["groupID"]}}}}
        raise AssertionError(f"unexpected request: {name}")

    @property
    def writes(self):
        return [n for n, _ in self.calls if n in ("createGroup", "addUsersToGroup", "addResToGroup")]


def migrate(api, tmp_path, *args):
    report = tmp_path / "report.csv"
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        inst = MockClient.return_value
        inst.paginate.side_effect = api.paginate
        inst.execute.side_effect = api.execute
        result = runner.invoke(app, ["-s", SESSION, "group", "migrate", "--report", str(report), *args])
    rows = list(csv.DictReader(report.open())) if report.exists() else []
    return result, rows


def two_groups_api(**kw):
    return Api(
        [group("s1", "Eng"), group("s2", "Ops"), group("m1", "Manual one", "MANUAL"), group("s3", "Old", active=False)],
        users={"s1": ["u1", "u2", "u3", "u4", "u5"], "s2": ["u1"]},
        resources={"s1": ["r1", "r2", "r3"], "s2": []},
        **kw,
    )


class TestDryRun:
    def test_completes_and_changes_nothing(self, tmp_path):
        api = two_groups_api()
        result, _ = migrate(api, tmp_path)
        assert result.exit_code == 0, result.output
        assert "DRY RUN" in result.output and api.writes == []

    def test_counts_every_member_and_resource_across_pages(self, tmp_path):
        result, rows = migrate(two_groups_api(page=2), tmp_path)
        by_source = {r["source_group_id"]: r for r in rows}
        assert (by_source["s1"]["user_count"], by_source["s1"]["resource_count"]) == ("5", "3")
        assert (by_source["s2"]["user_count"], by_source["s2"]["resource_count"]) == ("1", "0")
        assert "members: 5   resources: 3" in result.output

    def test_report_marks_dry_run_and_skips_inactive_and_manual_groups(self, tmp_path):
        _, rows = migrate(two_groups_api(), tmp_path)
        statuses = {r["source_group_id"]: r["status"] for r in rows}
        assert statuses == {"s1": "dry-run", "s2": "dry-run", "s3": "skipped-inactive"}
        assert {r["target_group_name"] for r in rows if r["status"] == "dry-run"} == {"Eng (Manual)", "Ops (Manual)"}

    def test_summary_line_counts_groups(self, tmp_path):
        result, _ = migrate(two_groups_api(), tmp_path)
        assert "Found 4 total groups: 2 active synced, 1 inactive synced (will be skipped)." in result.output

    def test_no_synced_groups_writes_no_report(self, tmp_path):
        result, rows = migrate(Api([group("m1", "Manual", "MANUAL")]), tmp_path)
        assert result.exit_code == 0 and rows == []


class TestExecute:
    def test_creates_a_manual_group_per_synced_group_and_copies_members_and_resources(self, tmp_path):
        api = two_groups_api()
        result, rows = migrate(api, tmp_path, "--execute")
        assert result.exit_code == 0, result.output
        assert [c["groupName"] for c in api.created] == ["Eng (Manual)", "Ops (Manual)"]
        assert api.user_chunks == [("new-1", ["u1", "u2", "u3", "u4", "u5"]), ("new-2", ["u1"])]
        assert api.resource_chunks == [("new-1", ["r1", "r2", "r3"])]  # Ops has none, so nothing to add
        assert {r["source_group_id"]: (r["status"], r["target_group_id"]) for r in rows if r["status"] != "skipped-inactive"} == {
            "s1": ("success", "new-1"), "s2": ("success", "new-2")}

    def test_new_groups_start_empty_and_are_filled_afterwards(self, tmp_path):
        api = two_groups_api()
        migrate(api, tmp_path, "--execute")
        assert all(c["userIDS"] == [] and c["resourceIDS"] == [] for c in api.created)

    def test_custom_name_suffix(self, tmp_path):
        api = two_groups_api()
        migrate(api, tmp_path, "--execute", "--name-suffix", " [copy]")
        assert [c["groupName"] for c in api.created] == ["Eng [copy]", "Ops [copy]"]

    def test_inactive_groups_are_never_touched(self, tmp_path):
        api = two_groups_api()
        migrate(api, tmp_path, "--execute")
        assert not any(c["groupName"].startswith("Old") for c in api.created)

    def test_large_groups_are_added_in_batches_of_200(self, tmp_path):
        users = [f"u{i}" for i in range(450)]
        api = Api([group("s1", "Big")], users={"s1": users}, resources={"s1": [f"r{i}" for i in range(201)]}, page=50)
        result, rows = migrate(api, tmp_path, "--execute")
        assert result.exit_code == 0, result.output
        assert [len(ids) for _, ids in api.user_chunks] == [200, 200, 50]
        assert [len(ids) for _, ids in api.resource_chunks] == [200, 1]
        assert sum((ids for _, ids in api.user_chunks), []) == users
        assert rows[0]["user_count"] == "450" and rows[0]["resource_count"] == "201"

    def test_an_existing_manual_group_with_the_target_name_is_reused(self, tmp_path):
        api = Api([group("s1", "Eng"), group("m9", "Eng (Manual)", "MANUAL")], users={"s1": ["u1"]}, resources={"s1": ["r1"]})
        result, rows = migrate(api, tmp_path, "--execute")
        assert result.exit_code == 0 and api.created == []
        assert api.user_chunks == [("m9", ["u1"])] and api.resource_chunks == [("m9", ["r1"])]
        assert "reused existing: m9" in result.output
        assert [(r["status"], r["target_group_id"]) for r in rows] == [("success", "m9")]

    def test_running_it_twice_does_not_create_duplicates(self, tmp_path):
        api = two_groups_api()
        migrate(api, tmp_path, "--execute")
        api.groups += [group(f"new-{i + 1}", c["groupName"], "MANUAL") for i, c in enumerate(api.created)]
        first = len(api.created)
        migrate(api, tmp_path, "--execute")
        assert len(api.created) == first


class TestSecurityPolicy:
    def test_the_source_groups_policy_is_copied_by_default(self, tmp_path):
        api = Api([group("s1", "Eng", policy={"id": "pol-A", "name": "A"}), group("s2", "Ops", policy={"id": "pol-B", "name": "B"})])
        migrate(api, tmp_path, "--execute")
        assert [c["securityPolicyId"] for c in api.created] == ["pol-A", "pol-B"]

    def test_no_copy_flag_creates_groups_without_a_policy(self, tmp_path):
        api = Api([group("s1", "Eng")])
        migrate(api, tmp_path, "--execute", "--no-copy-security-policy")
        assert [c["securityPolicyId"] for c in api.created] == [None]

    def test_a_group_without_a_policy_is_created_without_one(self, tmp_path):
        api = Api([group("s1", "Eng", policy=None)])
        migrate(api, tmp_path, "--execute")
        assert [c["securityPolicyId"] for c in api.created] == [None]


class TestFailures:
    def test_a_failed_create_is_reported_and_the_rest_continue(self, tmp_path):
        api = two_groups_api()
        api.create_error = "Name already taken"
        result, rows = migrate(api, tmp_path, "--execute")
        assert result.exit_code == 1 and "2 group(s) had errors" in result.output
        errors = [r for r in rows if r["status"] == "error"]
        assert len(errors) == 2 and all("groupCreate failed: Name already taken" in r["error"] for r in errors)

    def test_a_failure_in_one_group_does_not_stop_the_others(self, tmp_path):
        api = two_groups_api()
        real = api.execute
        calls = {"n": 0}

        def flaky(query, variables=None):
            if "mutation createGroup" in query:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise TwingateAPIError("boom")
            return real(query, variables)

        api.execute = flaky
        result, rows = migrate(api, tmp_path, "--execute")
        by = {r["source_group_id"]: r for r in rows}
        assert by["s1"]["status"] == "error" and "boom" in by["s1"]["error"] and by["s2"]["status"] == "success"
        assert result.exit_code == 1

    def test_a_failed_add_users_is_reported(self, tmp_path):
        api = two_groups_api()
        api.users_error = "User not found"
        result, rows = migrate(api, tmp_path, "--execute")
        assert result.exit_code == 1 and any("adding users failed: User not found" in r["error"] for r in rows)

    def test_a_failed_add_resources_is_reported(self, tmp_path):
        api = two_groups_api()
        api.resources_error = "Resource not found"
        _, rows = migrate(api, tmp_path, "--execute")
        assert any("adding resources failed: Resource not found" in r["error"] for r in rows)

    def test_the_report_is_still_written_when_groups_fail(self, tmp_path):
        api = two_groups_api()
        api.create_error = "nope"
        _, rows = migrate(api, tmp_path, "--execute")
        assert len(rows) == 3  # two failed groups plus the skipped inactive one

    def test_an_authentication_error_on_the_first_request_exits_cleanly(self, tmp_path):
        api = two_groups_api()
        api.list_error = TwingateAuthError("Bad token")
        result, rows = migrate(api, tmp_path, "--execute")
        assert result.exit_code == 1 and "Authentication error: Bad token" in result.output and api.writes == []
        assert "Traceback" not in result.output

    def test_an_api_error_while_listing_groups_exits_cleanly_and_writes_nothing(self, tmp_path):
        api = two_groups_api()
        api.list_error = TwingateAPIError("Rate limit exceeded")
        result, _ = migrate(api, tmp_path, "--execute")
        assert result.exit_code == 1 and "API error: Rate limit exceeded" in result.output and api.writes == []

    def test_an_error_reading_one_groups_members_is_recorded_and_the_run_continues(self, tmp_path):
        api = two_groups_api()
        real = api.execute
        seen = {"users": 0}

        def flaky(query, variables=None):
            if "query groupUsers" in query:
                seen["users"] += 1
                if variables["id"] == "s1":
                    raise TwingateAPIError("read failed")
            return real(query, variables)

        api.execute = flaky
        result, rows = migrate(api, tmp_path, "--execute")
        by = {r["source_group_id"]: r for r in rows}
        assert by["s1"]["status"] == "error" and "read failed" in by["s1"]["error"]
        assert by["s2"]["status"] == "success"
        assert result.exit_code == 1 and [c["groupName"] for c in api.created] == ["Ops (Manual)"]  # nothing half-made for s1


def test_the_default_report_name_is_timestamped_in_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    api = two_groups_api()
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.paginate.side_effect = api.paginate
        MockClient.return_value.execute.side_effect = api.execute
        result = runner.invoke(app, ["-s", SESSION, "group", "migrate"])
    assert result.exit_code == 0
    (report,) = list(tmp_path.glob("group_migration_report_*.csv"))
    assert re.fullmatch(r"group_migration_report_\d{8}T\d{6}Z\.csv", report.name)
