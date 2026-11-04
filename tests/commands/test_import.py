"""tgcli import: a dry run by default, a per-row report, and exit codes a script can rely on."""

from __future__ import annotations

import csv
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.importer.ca_material import pem, x509_fingerprint
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
        result, report = run(backup(tmp_path, [NETWORK], extra=["users.json", "connectors.json"]), FakeApi())
        assert "Not carried over (see the report for the reasons)" in result.output
        assert "users: Not created (0 users in the backup): users come from the identity provider" in result.output
        assert "connectors: Not created (0 Connectors in the backup)" in result.output
        assert [(r["kind"], r["name"], r["status"]) for r in rows_of(report) if r["kind"] == "not carried over"] == [
            ("not carried over", "users", "not carried over"), ("not carried over", "connectors", "not carried over")]

    def test_rows_that_already_exist_are_not_listed_but_are_counted(self, tmp_path):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}])
        result, report = run(backup(tmp_path, [NETWORK]), api)
        assert "remote networks         1 exists" in result.output and "exists       remote network" not in result.output
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

    def test_a_csv_with_service_accounts_grants_them_and_a_rerun_does_nothing(self, tmp_path):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], service_accounts=[{"id": "S1", "name": "ci"}], groups=[{"id": "G1", "name": "Eng", "type": "MANUAL"}])
        (tmp_path / "resources.csv").write_text(
            "name,network,address,groups,service_accounts\nWiki,HQ,wiki.internal,Eng,ci;ghost\n", encoding="utf-8")
        result, report = run(tmp_path, api, "--execute")
        assert result.exit_code == 0, result.output
        (row,) = rows_of(report)
        assert row["status"] == "created" and "access for 1 group and 1 service account" in row["detail"]
        assert row["warnings"] == "access for service account 'ghost' not added: no such service account in this tenant or in the file"
        assert sorted(api.resources[0]["access"]) == ["G1", "S1"]
        count = len(api.writes)
        result, report = run(tmp_path, api, "--execute")
        assert result.exit_code == 0 and len(api.writes) == count

    def test_a_backup_service_account_with_a_setting_the_api_refuses_is_left_out_and_said_so(self, tmp_path):
        api = FakeApi(networks=[{"id": "N1", "name": "HQ"}], service_accounts=[{"id": "S1", "name": "ci"}])
        resource = {**RESOURCE, "access": [{"principal": {"type": "ServiceAccount", "name": "ci"}, "expiresAt": "2999-01-01T00:00:00Z"}]}
        result, report = run(backup(tmp_path, [NETWORK], [], [resource]), api, "--execute")
        (_, wiki) = rows_of(report)
        assert wiki["status"] == "created" and "an expiry" in wiki["warnings"] and api.resources[0]["access"] == {}

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


class TestDevices:
    def folder(self, tmp_path, text):
        (tmp_path / "devices.csv").write_text(text, encoding="utf-8")
        return tmp_path

    def devices(self):
        return [
            {"id": "D1", "serialNumber": "ABC123", "isTrusted": False, "activeState": "ACTIVE", "user": {"email": "ann@x.com"}},
            {"id": "D2", "serialNumber": "OLD", "isTrusted": False, "activeState": "ARCHIVED", "user": {"email": "ann@x.com"}},
        ]

    def test_a_dry_run_reports_what_would_change_and_changes_nothing(self, tmp_path):
        api = FakeApi(devices=self.devices())
        result, report = run(self.folder(tmp_path, "serial_number,trusted\nabc123,true\nOLD,true\nNEW,true\n"), api)
        assert result.exit_code == 0, result.output
        assert api.writes == [] and api.devices[0]["isTrusted"] is False
        assert [(r["kind"], r["name"], r["status"]) for r in rows_of(report)] == [
            ("device", "abc123", "would-update"), ("device", "OLD", "skipped"), ("device", "NEW", "skipped")]
        assert "devices                 2 skipped, 1 would-update" in result.output

    def test_execute_changes_the_trust_and_the_report_lists_the_device_ids(self, tmp_path):
        api = FakeApi(devices=self.devices())
        result, report = run(self.folder(tmp_path, "serial_number,trusted\nABC123,true\n"), api, "--execute")
        assert result.exit_code == 0 and api.devices[0]["isTrusted"] is True
        assert (rows_of(report)[0]["status"], rows_of(report)[0]["id"]) == ("updated", "D1")

    def test_a_change_the_api_did_not_apply_exits_1(self, tmp_path):
        api = FakeApi(devices=self.devices())
        api.ignore_trust = True
        result, report = run(self.folder(tmp_path, "serial_number,trusted\nABC123,true\n"), api, "--execute")
        assert result.exit_code == 1 and rows_of(report)[0]["status"] == "error"

    def test_a_serial_that_has_not_registered_is_not_a_failure(self, tmp_path):
        result, _ = run(self.folder(tmp_path, "serial_number\nNEW\n"), FakeApi(), "--execute")
        assert result.exit_code == 0


class TestSync:
    TENANT = dict(
        networks=[{"id": "N1", "name": "HQ"}], users=USERS, groups=[{"id": "G1", "name": "Eng", "type": "MANUAL"}, {"id": "G2", "name": "Ops", "type": "MANUAL"}],
        resources=[{"id": "R1", "name": "Wiki", "network": "HQ", "alias": "old", "access": {"G2": {"principalId": "G2"}}}],
    )

    def files(self, tmp_path):
        return backup(tmp_path, resources=[{**RESOURCE, "alias": "wiki", "access": [{"principal": {"type": "Group", "name": "Eng"}}]}])

    def test_prune_without_sync_is_refused_before_anything_is_read(self, tmp_path):
        api = FakeApi(**self.TENANT)
        result, _ = run(self.files(tmp_path), api, "--prune")
        assert result.exit_code == 1 and "only works together with --sync" in result.output
        assert api.requests == []

    def test_a_dry_run_says_what_prune_would_remove_and_changes_nothing(self, tmp_path):
        api = FakeApi(**self.TENANT)
        result, report = run(self.files(tmp_path), api, "--sync", "--prune")
        assert result.exit_code == 0 and "DRY RUN" in result.output
        assert "--prune would REMOVE 0 group member(s) and 1 resource access grant(s)" in result.output
        assert api.writes == []
        (row,) = rows_of(report)
        assert row["status"] == "would-update" and row["detail"] == "already exists; access to add for 1 group; change alias; access to remove for 1 principal (Ops)"

    def test_without_sync_the_same_file_only_adds(self, tmp_path):
        api = FakeApi(**self.TENANT)
        result, report = run(self.files(tmp_path), api, "--execute")
        assert result.exit_code == 0 and "REMOVE" not in result.output
        assert set(api.resources[0]["access"]) == {"G1", "G2"} and api.resources[0]["alias"] == "old"

    def test_execute_changes_adds_and_removes_and_the_report_says_so(self, tmp_path):
        api = FakeApi(**self.TENANT)
        result, report = run(self.files(tmp_path), api, "--sync", "--prune", "--execute")
        assert result.exit_code == 0, result.output
        assert set(api.resources[0]["access"]) == {"G1"} and api.resources[0]["alias"] == "wiki"
        assert rows_of(report)[0]["status"] == "updated"
        again, _ = run(self.files(tmp_path), api, "--sync", "--prune", "--execute")
        assert again.exit_code == 0 and "REMOVE" not in again.output


class TestCarryingABackupToAnotherTenant:
    ROOT = pem("root")
    CA = {"id": "C1", "name": "Root", "type": "x509", "fingerprint": x509_fingerprint("root")}
    GATEWAY = {"id": "GW", "address": "gw.example.com", "remoteNetwork": {"id": "N", "name": "HQ"}, "x509CA": CA, "sshCA": None}

    def folder(self, tmp_path):
        backup(tmp_path, [NETWORK], extra=["users.json", "connectors.json", "security-policies.json", "devices.json"])
        (tmp_path / "manifest.json").write_text("{}")
        (tmp_path / "service-accounts.json").write_text(json.dumps([{"name": "ci", "keys": [{"id": "k"}]}]))
        (tmp_path / "certificate-authorities.json").write_text(json.dumps([self.CA]))
        (tmp_path / "gateways.json").write_text(json.dumps([self.GATEWAY]))
        (tmp_path / "dns-profiles.json").write_text(json.dumps([{"name": "Kids", "priority": 1}]))
        return tmp_path

    def certs(self, tmp_path, **named):
        folder = tmp_path / "certs"
        folder.mkdir()
        for name, text in named.items():
            (folder / name).write_text(text)
        return folder

    def test_a_dry_run_shows_everything_that_would_be_made_and_what_cannot_be_carried(self, tmp_path):
        (tmp_path / "backup").mkdir()
        api = FakeApi()
        result, report = run(self.folder(tmp_path / "backup"), api, "--ca-files", str(self.certs(tmp_path, **{"root.pem": self.ROOT})))
        assert result.exit_code == 0, result.output
        assert "Read 1 certificate file(s)" in result.output and "DRY RUN" in result.output and api.writes == []
        for kind in ("service accounts  ", "certificate authorities 1 would-create", "gateways          ", "dns profiles      "):
            assert kind in result.output
        carried = [r["name"] for r in rows_of(report) if r["kind"] == "not carried over"]
        assert carried == ["users", "connectors", "security policies", "device registrations", "service account keys"]

    def test_executing_makes_it_all_and_a_rerun_changes_nothing(self, tmp_path):
        (tmp_path / "backup").mkdir()
        folder = self.folder(tmp_path / "backup")
        api = FakeApi()
        certs = str(self.certs(tmp_path, **{"root.pem": self.ROOT}))
        result, report = run(folder, api, "--ca-files", certs, "--execute")
        assert result.exit_code == 0, result.output
        assert [r["status"] for r in rows_of(report) if r["kind"] != "not carried over"] == ["created"] * 5
        assert [g["address"] for g in api.gateways] == ["gw.example.com"] and [a["name"] for a in api.service_accounts] == ["ci"] and api.dns_profiles
        count = len(api.writes)
        result, report = run(folder, api, "--ca-files", certs, "--execute")
        assert result.exit_code == 0 and len(api.writes) == count

    def test_without_certificate_files_the_gateway_is_blocked_and_the_exit_code_says_so(self, tmp_path):
        (tmp_path / "backup").mkdir()
        result, report = run(self.folder(tmp_path / "backup"), FakeApi(), "--execute")
        assert result.exit_code == 1 and "blocked" in result.output
        by = {r["kind"]: r for r in rows_of(report)}
        assert by["certificate authority"]["status"] == "skipped" and by["gateway"]["status"] == "blocked"
        assert "--ca-files" in by["gateway"]["detail"]
        assert "certificate authorities" in [r["name"] for r in rows_of(report) if r["kind"] == "not carried over"]

    def test_a_ca_files_path_that_does_not_exist_stops_before_anything_is_read_or_written(self, tmp_path):
        (tmp_path / "backup").mkdir()
        api = FakeApi()
        result, _ = run(self.folder(tmp_path / "backup"), api, "--ca-files", str(tmp_path / "nowhere"), "--execute")
        assert result.exit_code == 1 and "does not exist. Nothing was changed." in result.output and api.requests == []

    def test_a_private_key_in_the_folder_is_refused_and_reported_and_never_sent(self, tmp_path):
        (tmp_path / "backup").mkdir()
        certs = self.certs(tmp_path, **{"root.pem": self.ROOT, "root.key": "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n"})
        api = FakeApi()
        result, report = run(self.folder(tmp_path / "backup"), api, "--ca-files", str(certs), "--execute")
        assert "holds a private key" in result.output
        assert not any("PRIVATE" in json.dumps(v) for _, v in api.writes)
        assert [r["name"] for r in rows_of(report) if r["kind"] == "not carried over"][-1] == "certificate files"
