"""tgcli restore: a dry run by default, a safety snapshot before any write, the guards, and exit codes a script can rely on."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.test_restore import ENG, HQ, WIKI, full_world, grant, read, resource, to_api
from tgcli.backup import Collected, write_backup
from tgcli.client.exceptions import TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app
from tgcli.queries.backup import ENTITIES
from tgcli.restore import READ_KEYS

runner = CliRunner()
SESSION = "TestSess"
URL = "https://acme.twingate.com/api/graphql/"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring, tmp_path, monkeypatch):
    SessionManager.store(SESSION, "acme", "tok-test")
    monkeypatch.chdir(tmp_path)  # a snapshot with no --snapshot-dir goes to the current folder, which must not be the repository


def collected_from(items: dict, problems=()) -> Collected:
    """What a full read of a tenant holding ``items`` gives; the types the test does not model are 'unreadable', so they are left out of a snapshot."""
    missing = {e.key: "not modelled" for e in ENTITIES if e.key not in items}
    return Collected(items={k: v for k, v in items.items()}, problems=list(problems), unreadable=missing)


def make_backup(tmp_path: Path, items: dict | None = None, tenant: str = "acme", now: datetime | None = None) -> Path:
    items = items or full_world()
    out = tmp_path / "bk"
    write_backup(collected_from({k: items[k] for k in ("groups", "users", "resources", "remote_networks")}), out, SESSION, tenant, now=now)
    return out


class Run:
    def __init__(self, tmp_path, api, current=None, problems=(), tenant_url=URL):
        self.tmp_path, self.api, self.problems, self.tenant_url = tmp_path, api, problems, tenant_url
        self.reads: list = []

    def collect(self, client, progress=None, keys=None):
        self.reads.append(keys)
        return collected_from({k: v for k, v in read(self.api).items() if keys is None or k in keys}, self.problems) if keys else collected_from(read(self.api), self.problems)

    def __call__(self, backup, *args, report="report.csv"):
        argv = ["-s", SESSION, "restore", str(backup), "--report", str(self.tmp_path / report), *args]
        with patch("tgcli.commands._common.TwingateClient") as MockClient, patch("tgcli.commands.restore.collect", side_effect=self.collect):
            MockClient.return_value.url = self.tenant_url
            MockClient.return_value.execute.side_effect = self.api.execute
            return runner.invoke(app, argv)


def damaged_api():
    api = to_api(full_world())
    api.groups[0]["name"] = "Engineering"
    api.resources[0]["access"] = {}
    return api


def rows_of(path: Path):
    """The report's rows for things that were not already right (it lists every object, the unchanged ones as 'exists')."""
    with open(path, newline="", encoding="utf-8") as handle:
        return [r for r in csv.DictReader(handle) if r["status"] != "exists"]


class TestDryRun:
    def test_it_is_the_default_and_changes_and_writes_nothing(self, tmp_path):
        api = damaged_api()
        run = Run(tmp_path, api)
        result = run(make_backup(tmp_path))
        assert result.exit_code == 0, result.output
        assert api.writes == [] and "DRY RUN" in result.output and "--execute" in result.output
        assert [(r["kind"], r["name"], r["status"]) for r in rows_of(tmp_path / "report.csv")] == [
            ("group", "Eng", "would-update"), ("resource", "Wiki", "would-update")]
        assert not list(tmp_path.glob("twingate-prerestore-*"))

    def test_it_reads_only_what_it_needs(self, tmp_path):
        run = Run(tmp_path, damaged_api())
        run(make_backup(tmp_path))
        assert run.reads == [READ_KEYS]

    def test_a_tenant_that_matches_says_so(self, tmp_path):
        result = Run(tmp_path, to_api(full_world()))(make_backup(tmp_path))
        assert result.exit_code == 0 and "Nothing differs from the backup" in result.output

    def test_what_was_not_compared_and_what_was_left_alone_are_named(self, tmp_path):
        api = to_api(full_world())
        api.groups.append({"id": "G9", "name": "New", "type": "MANUAL", "isActive": True, "members": set(), "securityPolicyId": None})
        result = Run(tmp_path, api)(make_backup(tmp_path))
        assert "Created since the backup, and left alone (restore never deletes): 1 groups." in result.output
        assert "Not compared:" in result.output and "devices (not in this backup)" in result.output
        assert "security policies (not in this backup)" in result.output

    def test_warnings_are_counted_and_attributed_to_the_backup(self, tmp_path):
        items = full_world()
        items["resources"] = [{**WIKI, "approverGroups": [{"id": "G9", "name": "Ghost"}]}]
        api = to_api({**items, "resources": [{**WIKI, "alias": None}]})
        result = Run(tmp_path, api)(make_backup(tmp_path, items))
        assert "1 warning(s): something in the backup was left out of a row" in result.output

    def test_prune_says_what_it_would_remove(self, tmp_path):
        api = to_api(full_world())
        api.groups[0]["members"].add("U4")
        result = Run(tmp_path, api)(make_backup(tmp_path), "--prune")
        assert "--prune would REMOVE 1 group member(s) and 0 resource access grant(s)" in result.output
        assert api.writes == []

    def test_a_big_restore_warns_about_the_rate_limit(self, tmp_path):
        items = full_world()
        items["groups"] = [{**ENG, "id": f"G{i}", "name": f"Group{i}"} for i in range(30)]
        items["resources"] = []
        run = Run(tmp_path, to_api({**items, "groups": []}))
        result = run(make_backup(tmp_path, items))
        assert "Applying would make" in result.output and "write requests" in result.output


class TestExecute:
    def test_the_tenant_is_snapshotted_first_and_then_repaired(self, tmp_path):
        api = damaged_api()
        snapshot = tmp_path / "snap"
        result = Run(tmp_path, api)(make_backup(tmp_path), "--execute", "--snapshot-dir", str(snapshot))
        assert result.exit_code == 0, result.output
        assert (snapshot / "manifest.json").is_file() and f"tgcli restore {snapshot} --execute" in result.output
        assert result.output.index("Safety snapshot") < result.output.index("Applying")
        assert [name for name, _ in api.writes] == ["importGroupSync", "importAccess"]
        assert api.groups[0]["name"] == "Eng" and set(api.resources[0]["access"]) == {"G1", "G2"}
        assert {r["status"] for r in rows_of(tmp_path / "report.csv")} == {"updated"}

    def test_the_snapshot_holds_the_damaged_state_so_restoring_from_it_undoes_the_restore(self, tmp_path):
        api = damaged_api()
        snapshot = tmp_path / "snap"
        Run(tmp_path, api)(make_backup(tmp_path), "--execute", "--snapshot-dir", str(snapshot))
        saved = json.loads((snapshot / "groups.json").read_text(encoding="utf-8"))
        assert "Engineering" in [g["name"] for g in saved] and "Eng" not in [g["name"] for g in saved]

    def test_it_reads_everything_because_what_it_reads_is_the_snapshot(self, tmp_path):
        run = Run(tmp_path, damaged_api())
        run(make_backup(tmp_path), "--execute", "--snapshot-dir", str(tmp_path / "snap"))
        assert run.reads == [None]

    def test_the_snapshot_can_be_left_out(self, tmp_path):
        api = damaged_api()
        result = Run(tmp_path, api)(make_backup(tmp_path), "--execute", "--no-snapshot")
        assert result.exit_code == 0 and "Safety snapshot" not in result.output and api.writes
        assert not list(tmp_path.glob("twingate-prerestore-*"))

    def test_a_snapshot_folder_that_exists_stops_everything_before_any_write(self, tmp_path):
        api = damaged_api()
        (tmp_path / "snap").mkdir()
        run = Run(tmp_path, api)
        result = run(make_backup(tmp_path), "--execute", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 1 and "already exists" in result.output and api.writes == []
        assert run.reads == []  # it stops before reading the tenant

    def test_a_tenant_read_with_problems_is_not_restored_to(self, tmp_path):
        api = damaged_api()
        run = Run(tmp_path, api, problems=["groups: API reports 3, backed up 2"])
        result = run(make_backup(tmp_path), "--execute", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 1 and "could not be read completely" in result.output and api.writes == []
        assert not (tmp_path / "snap").exists()

    def test_a_dry_run_only_warns_about_a_tenant_read_with_problems(self, tmp_path):
        run = Run(tmp_path, damaged_api(), problems=["groups: API reports 3, backed up 2"])
        result = run(make_backup(tmp_path))
        assert result.exit_code == 0 and "plan may be wrong" in result.output

    def test_a_failed_write_exits_1_and_the_report_says_which(self, tmp_path):
        api = damaged_api()
        api.fail["importGroupSync"] = "refused"
        result = Run(tmp_path, api)(make_backup(tmp_path), "--execute", "--no-snapshot")
        assert result.exit_code == 1 and "failed or were blocked" in result.output
        assert [(r["name"], r["status"]) for r in rows_of(tmp_path / "report.csv")] == [("Eng", "error"), ("Wiki", "updated")]

    def test_a_blocked_row_fails_a_dry_run_too(self, tmp_path):
        api = to_api(full_world())
        eng = api.groups[0]
        api.groups[0:1] = [{**eng, "id": "G98"}, {**eng, "id": "G99"}]  # the ID is gone and two groups now have the name
        for res in api.resources:
            res["access"].pop("G1", None)
        result = Run(tmp_path, api)(make_backup(tmp_path))
        assert result.exit_code == 1 and "are blocked and would not be restored" in result.output
        assert [(r["name"], r["status"]) for r in rows_of(tmp_path / "report.csv")] == [("Eng", "blocked")]

    def test_a_rejected_login_exits_1(self, tmp_path):
        run = Run(tmp_path, damaged_api())
        with patch("tgcli.commands._common.TwingateClient") as MockClient, patch("tgcli.commands.restore.collect", side_effect=TwingateAuthError("bad key")):
            MockClient.return_value.url = URL
            result = runner.invoke(app, ["-s", SESSION, "restore", str(make_backup(tmp_path)), "--report", str(tmp_path / "r.csv")])
        assert result.exit_code == 1 and "Authentication error: bad key" in result.output and run.api.writes == []


class TestGuards:
    def test_a_backup_of_another_tenant_is_refused_before_anything_is_read(self, tmp_path):
        run = Run(tmp_path, damaged_api())
        result = run(make_backup(tmp_path, tenant="other"), "--execute")
        assert result.exit_code == 1 and "'other'" in result.output and "tgcli import" in result.output
        assert run.reads == [] and run.api.writes == []

    def test_force_tenant_overrides_it(self, tmp_path):
        run = Run(tmp_path, damaged_api())
        assert run(make_backup(tmp_path, tenant="other"), "--force-tenant").exit_code == 0

    def test_a_backup_whose_files_were_changed_is_not_restored_from(self, tmp_path):
        backup = make_backup(tmp_path)
        (backup / "groups.json").write_text("[]\n", encoding="utf-8")
        api = damaged_api()
        result = Run(tmp_path, api)(backup, "--execute")
        assert result.exit_code == 1 and "does not match its own checksums" in result.output and api.writes == []

    def test_a_dry_run_of_such_a_backup_only_warns(self, tmp_path):
        backup = make_backup(tmp_path)
        (backup / "groups.json").write_text("[]\n", encoding="utf-8")
        result = Run(tmp_path, damaged_api())(backup)
        assert result.exit_code == 0 and "does not match the checksum" in result.output

    def test_an_old_backup_is_called_out(self, tmp_path):
        old = datetime.now(timezone.utc) - timedelta(days=90)
        result = Run(tmp_path, damaged_api())(make_backup(tmp_path, now=old))
        assert "90 days old" in result.output

    def test_something_that_is_not_a_backup_is_refused(self, tmp_path):
        (tmp_path / "bk").mkdir()
        result = Run(tmp_path, damaged_api())(tmp_path / "bk")
        assert result.exit_code == 1 and "not a `tgcli backup` folder" in result.output

    def test_an_unwritable_report_path_stops_everything_first(self, tmp_path):
        api = damaged_api()
        result = Run(tmp_path, api)(make_backup(tmp_path), "--execute", report="no/such/dir/report.csv")
        assert result.exit_code == 1 and "Nothing was changed" in result.output and api.writes == []


class TestOnly:
    def test_only_the_named_object_is_restored(self, tmp_path):
        api = damaged_api()
        result = Run(tmp_path, api)(make_backup(tmp_path), "--execute", "--no-snapshot", "--only", "group:Eng")
        assert result.exit_code == 0, result.output
        assert [name for name, _ in api.writes] == ["importGroupSync"]
        assert {r["name"]: r["status"] for r in rows_of(tmp_path / "report.csv")} == {"Eng": "updated", "Wiki": "skipped"}

    def test_it_matches_by_id_too_and_can_be_repeated(self, tmp_path):
        api = damaged_api()
        Run(tmp_path, api)(make_backup(tmp_path), "--execute", "--no-snapshot", "--only", "group:G1", "--only", "resource:Wiki")
        assert [name for name, _ in api.writes] == ["importGroupSync", "importAccess"]

    @pytest.mark.parametrize("selector, message", [("Eng", "should look like"), ("thing:Eng", "should look like"), ("group:", "should look like"), ("group:Nope", "matches nothing")])
    def test_a_selector_that_is_not_understood_stops_everything(self, tmp_path, selector, message):
        api = damaged_api()
        result = Run(tmp_path, api)(make_backup(tmp_path), "--execute", "--no-snapshot", "--only", selector)
        assert result.exit_code == 1 and message in result.output and api.writes == []


def make_full_backup(tmp_path: Path, items: dict) -> Path:
    out = tmp_path / "bk"
    keys = ("groups", "users", "resources", "remote_networks", "devices", "service_accounts", "gateways", "connectors", "dns_profiles", "certificate_authorities", "security_policies")
    write_backup(collected_from({k: items[k] for k in keys}), out, SESSION, "acme")
    return out


class TestIncludeAndTheNewTypes:
    def blocked_device_api(self):
        world = full_world()
        api = to_api(world)
        api.devices[0].update(isTrusted=False, activeState="BLOCKED")
        return world, api

    def test_an_unknown_include_is_refused_before_anything_is_read(self, tmp_path):
        run = Run(tmp_path, to_api(full_world()))
        result = run(make_backup(tmp_path), "--include", "everything")
        assert result.exit_code == 1 and "--include everything is not something restore can add" in result.output and run.reads == []

    def test_a_dry_run_says_how_many_devices_differ_and_how_to_restore_them(self, tmp_path):
        world, api = self.blocked_device_api()
        result = Run(tmp_path, api)(make_full_backup(tmp_path, world))
        assert result.exit_code == 0 and "1 device differ" in result.output and "--include devices" in result.output
        assert api.writes == []

    def test_a_dry_run_reads_devices_only_when_the_backup_has_them(self, tmp_path):
        world, api = self.blocked_device_api()
        run = Run(tmp_path, api)
        run(make_full_backup(tmp_path, world))
        assert "devices" in run.reads[0]
        other = tmp_path / "other"
        other.mkdir()
        run2 = Run(other, to_api(full_world()))
        run2(make_backup(other))
        assert "devices" not in run2.reads[0]

    def test_include_devices_restores_them_on_execute(self, tmp_path):
        world, api = self.blocked_device_api()
        result = Run(tmp_path, api)(make_full_backup(tmp_path, world), "--execute", "--include", "devices", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 0, result.output
        assert api.devices[0]["isTrusted"] is True and api.devices[0]["activeState"] == "ACTIVE"
        assert "device" in {r["kind"] for r in rows_of(tmp_path / "report.csv")}

    def test_without_include_an_execute_leaves_devices_and_roles_alone(self, tmp_path):
        world, api = self.blocked_device_api()
        api.users[0]["role"] = "ADMIN"
        result = Run(tmp_path, api)(make_full_backup(tmp_path, world), "--execute", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 0 and api.writes == []
        assert api.devices[0]["activeState"] == "BLOCKED" and api.users[0]["role"] == "ADMIN"

    def test_only_can_name_the_new_kinds(self, tmp_path):
        world = full_world()
        api = to_api(world)
        api.service_accounts[0]["name"] = "Hacked"
        api.connectors[0]["name"] = "oops"
        result = Run(tmp_path, api)(make_full_backup(tmp_path, world), "--execute", "--only", "service-account:Bot", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 0, result.output
        assert api.service_accounts[0]["name"] == "Bot" and api.connectors[0]["name"] == "oops"

    def test_the_summary_lists_the_new_kinds(self, tmp_path):
        world = full_world()
        api = to_api(world)
        api.connectors = []
        result = Run(tmp_path, api)(make_full_backup(tmp_path, world))
        assert "connectors" in result.output and "1 would-create" in result.output
