"""tgcli import: a dry run by default, a per-row report, and exit codes a script can rely on."""

from __future__ import annotations

import csv
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.importer.fake_api import FakeApi
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
USERS = [{"id": "U1", "email": "ann@x.com"}, {"id": "U2", "email": "bob@x.com"}]


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def backup(tmp_path, networks=(), groups=(), resources=(), extra=()):
    for name, data in (("remote-networks", networks), ("groups", groups), ("resources", resources)):
        if data:
            (tmp_path / f"{name}.json").write_text(json.dumps(list(data)), encoding="utf-8")
    for name in extra:
        (tmp_path / name).write_text("[]", encoding="utf-8")
    return tmp_path


def run(tmp_path, api, *args, session=True):
    report = tmp_path / "report.csv"
    argv = (["-s", SESSION] if session else []) + ["import", str(tmp_path), "--report", str(report), *args]
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.execute.side_effect = api.execute
        result = runner.invoke(app, argv)
    return result, report


def rows_of(report):
    with open(report, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


NETWORK = {"name": "HQ", "location": "AWS", "networkType": "REGULAR", "isActive": True}
GROUP = {"name": "Eng", "type": "MANUAL", "users": [{"email": "ann@x.com"}, {"email": "gone@x.com"}]}
RESOURCE = {
    "type": "NETWORK", "name": "Wiki", "remoteNetwork": {"name": "HQ"}, "address": {"value": "wiki.internal"},
    "access": [{"principal": {"type": "Group", "name": "Eng"}}],
}


class TestDryRun:
    def test_it_is_the_default_and_writes_nothing(self, tmp_path):
        api = FakeApi(users=USERS)
        result, report = run(backup(tmp_path, [NETWORK], [GROUP], [RESOURCE]), api)
        assert result.exit_code == 0, result.output
        assert api.writes == [] and "DRY RUN" in result.output and "--execute" in result.output
        assert [(r["kind"], r["name"], r["status"]) for r in rows_of(report)] == [
            ("remote network", "HQ", "would-create"), ("group", "Eng", "would-create"), ("resource", "Wiki", "would-create")]

    def test_warnings_are_shown_in_the_report_and_do_not_fail_the_run(self, tmp_path):
        api = FakeApi(users=USERS)
        result, report = run(backup(tmp_path, [NETWORK], [GROUP], [RESOURCE]), api)
        assert result.exit_code == 0 and "1 warning(s)" in result.output
        assert rows_of(report)[1]["warnings"] == "member not found: gone@x.com"

    def test_a_blocked_row_makes_the_exit_code_1_even_though_nothing_was_written(self, tmp_path):
        result, report = run(backup(tmp_path, resources=[RESOURCE]), FakeApi())
        assert result.exit_code == 1 and "1 row(s) are blocked and would not be imported" in result.output
        assert rows_of(report)[0]["status"] == "blocked" and "Remote Network 'HQ'" in rows_of(report)[0]["detail"]

    def test_a_big_import_says_how_many_writes_it_would_make(self, tmp_path):
        result, _ = run(backup(tmp_path, [{"name": f"n{i}"} for i in range(21)]), FakeApi())
        assert "Applying would make 21 write requests" in result.output

    def test_a_small_import_does_not_nag_about_rate_limits(self, tmp_path):
        result, _ = run(backup(tmp_path, [{"name": f"n{i}"} for i in range(20)]), FakeApi())
        assert "write requests" not in result.output

    def test_unused_backup_files_are_named(self, tmp_path):
        result, _ = run(backup(tmp_path, [NETWORK], extra=["users.json", "connectors.json"]), FakeApi())
        assert "Not imported (not supported yet): users.json, connectors.json." in result.output

    def test_rows_that_already_exist_are_not_listed_but_are_counted(self, tmp_path):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}])
        result, report = run(backup(tmp_path, [NETWORK]), api)
        assert "remote networks  1 exists" in result.output and "exists       remote network" not in result.output
        assert rows_of(report)[0]["status"] == "exists"

    def test_a_long_list_is_cut_in_the_terminal_but_not_in_the_report(self, tmp_path):
        networks = [{"name": f"n{i}"} for i in range(230)]
        result, report = run(backup(tmp_path, networks), FakeApi())
        assert "... and 30 more (see the report)" in result.output and len(rows_of(report)) == 230


class TestExecute:
    def test_it_applies_the_plan_and_reports_each_row(self, tmp_path):
        api = FakeApi(users=USERS)
        result, report = run(backup(tmp_path, [NETWORK], [GROUP], [RESOURCE]), api, "--execute")
        assert result.exit_code == 0, result.output
        assert "DRY RUN" not in result.output
        assert [(r["name"], r["status"]) for r in rows_of(report)] == [("HQ", "created"), ("Eng", "created"), ("Wiki", "created")]
        assert all(r["id"] for r in rows_of(report))
        assert api.groups[0]["members"] == {"U1"} and list(api.resources[0]["access"]) == [api.groups[0]["id"]]

    def test_running_it_again_changes_nothing(self, tmp_path):
        api = FakeApi(users=USERS)
        folder = backup(tmp_path, [NETWORK], [GROUP], [RESOURCE])
        run(folder, api, "--execute")
        count = len(api.writes)
        result, report = run(folder, api, "--execute")
        assert result.exit_code == 0 and len(api.writes) == count
        assert {r["status"] for r in rows_of(report)} == {"exists"}

    def test_a_failed_row_gives_exit_code_1_and_the_report_says_why(self, tmp_path):
        api = FakeApi(users=USERS)
        api.fail["importNetwork"] = "name not allowed"
        result, report = run(backup(tmp_path, [NETWORK], [GROUP]), api, "--execute")
        assert result.exit_code == 1 and "failed or were blocked" in result.output
        assert [(r["status"], r["error"]) for r in rows_of(report)] == [("error", "name not allowed"), ("created", "")]

    def test_synced_groups_are_never_written_to(self, tmp_path):
        api = FakeApi(users=USERS, groups=[{"id": "G1", "name": "Okta", "type": "SYNCED", "members": set()}])
        synced = {"name": "Okta", "type": "SYNCED", "users": [{"email": "ann@x.com"}]}
        result, report = run(backup(tmp_path, groups=[synced]), api, "--execute")
        assert result.exit_code == 0 and api.writes == [] and rows_of(report)[0]["status"] == "skipped"

    def test_the_report_is_written_even_when_the_credentials_are_rejected_part_way(self, tmp_path):
        api = FakeApi(users=USERS)
        api.raise_on["importGroup"] = TwingateAuthError("bad token")
        result, report = run(backup(tmp_path, [NETWORK], [GROUP], [RESOURCE]), api, "--execute")
        assert result.exit_code == 1
        assert [r["status"] for r in rows_of(report)] == ["created", "error", "not-run"]

    def test_unicode_and_awkward_names_survive_the_report(self, tmp_path):
        group = {"name": 'Ελληνικά, "quoted" 日本語', "type": "MANUAL", "users": []}
        result, report = run(backup(tmp_path, groups=[group]), FakeApi(), "--execute")
        assert result.exit_code == 0 and rows_of(report)[0]["name"] == group["name"]


class TestErrors:
    def test_an_unreadable_file_is_an_error_before_anything_else_happens(self, tmp_path):
        (tmp_path / "groups.json").write_text("{nope", encoding="utf-8")
        api = FakeApi()
        result, report = run(tmp_path, api)
        assert result.exit_code == 1 and "is not valid JSON" in result.output
        assert isinstance(result.exception, SystemExit)  # a clean exit, not a crash that happens to exit 1
        assert api.requests == [] and not report.exists()

    def test_a_folder_with_nothing_to_import(self, tmp_path):
        result, _ = run(tmp_path, FakeApi())
        assert result.exit_code == 1 and "has none of" in result.output

    def test_it_needs_a_session(self, tmp_path):
        result, _ = run(backup(tmp_path, [NETWORK]), FakeApi(), session=False)
        assert result.exit_code == 1 and "No session name provided" in result.output

    @pytest.mark.parametrize("error,message", [
        (TwingateAuthError("bad token"), "Authentication error: bad token"),
        (TwingateAPIError("HTTP 500"), "API error: HTTP 500"),
    ])
    def test_a_failure_while_reading_the_tenant_stops_before_any_write(self, tmp_path, error, message):
        api = FakeApi()
        api.raise_on["query"] = error
        result, report = run(backup(tmp_path, [NETWORK]), api)
        assert result.exit_code == 1 and message in result.output
        assert api.writes == [] and not report.exists()

    def test_the_default_report_goes_in_the_current_folder_with_a_timestamp(self, tmp_path, monkeypatch):
        (tmp_path / "in").mkdir()
        folder = backup(tmp_path / "in", [NETWORK])
        monkeypatch.chdir(tmp_path)
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.side_effect = FakeApi().execute
            result = runner.invoke(app, ["-s", SESSION, "import", str(folder)])
        assert result.exit_code == 0
        assert len(list(tmp_path.glob("import_report_*Z.csv"))) == 1
