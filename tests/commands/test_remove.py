"""tgcli remove: the list, the typed confirmation, the safety snapshot, and that a run with any problem removes nothing."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.test_removal import WORLD, FakeClient
from tgcli.backup import Collected
from tgcli.client.session import SessionManager
from tgcli.main import app
from tgcli.removal import READ_KEYS

runner = CliRunner()
SESSION = "TestSess"
URL = "https://acme.twingate.com/api/graphql/"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring, tmp_path, monkeypatch):
    SessionManager.store(SESSION, "acme", "tok-test")
    monkeypatch.chdir(tmp_path)  # a snapshot with no --snapshot-dir goes to the current folder, which must not be the repository


def world_items():
    return {**{k: [dict(i) for i in v] for k, v in WORLD.items()}, "users": [], "security_policies": [], "service_accounts": []}


class Run:
    def __init__(self, tmp_path, items=None, problems=(), terminal=True, answer="", client=None):
        self.tmp_path, self.items, self.problems, self.terminal, self.answer = tmp_path, items or world_items(), problems, terminal, answer
        self.client = client or FakeClient()
        self.reads: list = []

    def collect(self, client, progress=None, keys=None):
        self.reads.append(keys)
        return Collected(items={k: v for k, v in self.items.items() if keys is None or k in keys}, problems=list(self.problems))

    def __call__(self, file, *args, report="report.csv", input=None):
        argv = ["-s", SESSION, "remove", str(file), "--report", str(self.tmp_path / report), *args]
        with patch("tgcli.commands._common.TwingateClient") as MockClient, patch("tgcli.commands.remove.collect", side_effect=self.collect), patch(
            "tgcli.commands._common._at_a_terminal", return_value=self.terminal
        ):
            MockClient.return_value.url = URL
            MockClient.return_value.execute.side_effect = self.client.execute
            return runner.invoke(app, argv, input=self.answer if input is None else input)

    @property
    def deletes(self):
        return self.client.calls


def file(tmp_path, text, name="remove.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


GOOD = "kind,name\ngroup,Ops\nresource,Git\n"


def report_rows(path: Path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TestDryRun:
    def test_it_is_the_default_and_removes_nothing(self, tmp_path):
        run = Run(tmp_path)
        result = run(file(tmp_path, GOOD))
        assert result.exit_code == 0, result.output
        assert run.deletes == [] and "DRY RUN" in result.output and "--execute" in result.output
        assert "to-remove" in result.output and "Git" in result.output and "Ops" in result.output
        assert "Summary: 1 resource, 1 group to remove; 0 not found; 0 blocked." in result.output

    def test_it_reads_only_what_it_needs_and_writes_no_snapshot(self, tmp_path):
        run = Run(tmp_path)
        run(file(tmp_path, GOOD))
        assert run.reads == [READ_KEYS] and not list(tmp_path.glob("twingate-preremove-*"))

    def test_the_list_shows_what_depends_on_each_object(self, tmp_path):
        result = Run(tmp_path)(file(tmp_path, GOOD))
        assert "access for 1 group or service account is removed with it" in result.output and "2 members lose what it gave them" in result.output

    def test_the_report_lists_every_line(self, tmp_path):
        run = Run(tmp_path)
        run(file(tmp_path, GOOD + "group,Nope\n"))
        rows = report_rows(tmp_path / "report.csv")
        assert [(r["kind"], r["name"], r["status"]) for r in rows] == [("resource", "Git", "to-remove"), ("group", "Ops", "to-remove"), ("group", "Nope", "not-found")]

    def test_a_blocked_line_is_exit_1_even_in_a_dry_run(self, tmp_path):
        result = Run(tmp_path)(file(tmp_path, "kind,name\ngroup,Okta Staff\n"))
        assert result.exit_code == 1 and "blocked" in result.output and "identity provider" in result.output

    def test_not_found_alone_is_not_an_error(self, tmp_path):
        result = Run(tmp_path)(file(tmp_path, "kind,name\ngroup,Nope\n"))
        assert result.exit_code == 0 and "1 not found" in result.output

    def test_a_plain_list_with_kind(self, tmp_path):
        result = Run(tmp_path)(file(tmp_path, "Ops\nEng\n", "names.txt"), "--kind", "group")
        assert result.exit_code == 0 and "2 group" in result.output

    def test_a_plain_list_without_kind_blocks(self, tmp_path):
        result = Run(tmp_path)(file(tmp_path, "Ops\n", "names.txt"))
        assert result.exit_code == 1 and "needs --kind" in result.output

    def test_an_unknown_kind_option_is_refused_before_anything_is_read(self, tmp_path):
        run = Run(tmp_path)
        result = run(file(tmp_path, GOOD), "--kind", "connector")
        assert result.exit_code == 1 and "should be resource, group or network" in result.output and run.reads == []

    def test_a_read_with_problems_warns_on_a_dry_run(self, tmp_path):
        result = Run(tmp_path, problems=["groups: API reports 5, backed up 4"])(file(tmp_path, GOOD))
        assert result.exit_code == 0 and "could not be read completely" in result.output

    def test_a_long_list_is_cut_short_on_screen_but_not_in_the_report(self, tmp_path):
        items = world_items()
        items["groups"] = [{"id": f"G{i}", "name": f"g{i}", "type": "MANUAL", "users": [], "resources": []} for i in range(250)]
        text = "kind,name\n" + "".join(f"group,g{i}\n" for i in range(250))
        result = Run(tmp_path, items)(file(tmp_path, text))
        assert "... and 50 more (see the report)" in result.output and len(report_rows(tmp_path / "report.csv")) == 250


class TestConfirmation:
    def test_typing_the_count_removes_them(self, tmp_path):
        run = Run(tmp_path, answer="2\n")
        result = run(file(tmp_path, GOOD), "--execute", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 0, result.output
        assert run.deletes == [("resourceDelete", "R2"), ("groupDelete", "G2")]
        assert "Type 2 to confirm" in result.output and "from acme" in result.output and "1 resource, 1 group" in result.output
        assert {r["status"] for r in report_rows(tmp_path / "report.csv")} == {"removed"}

    @pytest.mark.parametrize("answer", ["y\n", "yes\n", "3\n", "1\n", "\n", "two\n", "2 2\n", "02\n", "-2\n"])
    def test_anything_but_the_exact_count_removes_nothing(self, tmp_path, answer):
        run = Run(tmp_path, answer=answer)
        result = run(file(tmp_path, GOOD), "--execute", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 1 and run.deletes == [] and "Nothing was removed." in result.output
        assert not (tmp_path / "snap").exists()

    def test_the_count_may_have_spaces_around_it(self, tmp_path):
        run = Run(tmp_path, answer=" 2 \n")
        assert run(file(tmp_path, GOOD), "--execute", "--no-snapshot").exit_code == 0 and len(run.deletes) == 2

    def test_closed_input_removes_nothing(self, tmp_path):
        run = Run(tmp_path, answer="")
        result = run(file(tmp_path, GOOD), "--execute", "--no-snapshot")
        assert result.exit_code == 1 and run.deletes == []

    def test_the_list_is_shown_before_the_question(self, tmp_path):
        result = Run(tmp_path, answer="2\n")(file(tmp_path, GOOD), "--execute", "--no-snapshot")
        assert result.output.index("What will be removed") < result.output.index("Git") < result.output.index("to confirm")

    def test_with_no_terminal_it_refuses_and_there_is_no_yes(self, tmp_path):
        run = Run(tmp_path, terminal=False)
        result = run(file(tmp_path, GOOD), "--execute")
        assert result.exit_code == 1 and run.deletes == [] and "no terminal to ask on" in result.output
        assert run(file(tmp_path, GOOD), "--execute", "--yes").exit_code == 2  # the option does not exist

    def test_piped_input_does_not_count_as_a_terminal_even_with_the_right_answer(self, tmp_path):
        run = Run(tmp_path, terminal=False, answer="2\n")
        assert run(file(tmp_path, GOOD), "--execute", "--no-snapshot").exit_code == 1 and run.deletes == []

    def test_nothing_to_remove_asks_nothing(self, tmp_path):
        run = Run(tmp_path, terminal=False)
        result = run(file(tmp_path, "kind,name\ngroup,Nope\n"), "--execute")
        assert result.exit_code == 0 and "Nothing to remove." in result.output and run.deletes == []


class TestSnapshot:
    def test_the_tenant_is_snapshotted_after_the_answer_and_before_the_first_delete(self, tmp_path):
        snap = tmp_path / "snap"
        run = Run(tmp_path, answer="2\n")
        result = run(file(tmp_path, GOOD), "--execute", "--snapshot-dir", str(snap))
        assert (snap / "manifest.json").is_file() and f"tgcli restore {snap} --execute" in result.output
        assert result.output.index("to confirm") < result.output.index("Safety snapshot") < result.output.index("Removing...")
        names = {n["name"] for n in json.loads((snap / "groups.json").read_text())}
        assert "Ops" in names  # the snapshot is what was read, before the removal

    def test_the_snapshot_holds_only_what_was_read(self, tmp_path):
        snap = tmp_path / "snap"
        Run(tmp_path, answer="2\n")(file(tmp_path, GOOD), "--execute", "--snapshot-dir", str(snap))
        manifest = json.loads((snap / "manifest.json").read_text())
        assert sorted(manifest["files"]) == ["groups.json", "remote-networks.json", "resources.json", "security-policies.json", "service-accounts.json", "users.json"]

    def test_the_default_snapshot_goes_in_the_current_folder_named_for_the_tenant(self, tmp_path):
        Run(tmp_path, answer="2\n")(file(tmp_path, GOOD), "--execute")
        assert [p.name.startswith("twingate-preremove-acme-") for p in tmp_path.glob("twingate-preremove-*")] == [True]

    def test_no_snapshot_skips_it(self, tmp_path):
        run = Run(tmp_path, answer="2\n")
        result = run(file(tmp_path, GOOD), "--execute", "--no-snapshot")
        assert result.exit_code == 0 and not list(tmp_path.glob("twingate-preremove-*")) and "Safety snapshot" not in result.output

    def test_an_existing_snapshot_folder_is_refused_before_anything_is_read(self, tmp_path):
        (tmp_path / "snap").mkdir()
        run = Run(tmp_path, answer="2\n")
        result = run(file(tmp_path, GOOD), "--execute", "--snapshot-dir", str(tmp_path / "snap"))
        assert result.exit_code == 1 and "already exists" in result.output and run.reads == [] and run.deletes == []

    def test_a_snapshot_that_cannot_be_written_stops_before_any_delete(self, tmp_path):
        run = Run(tmp_path, answer="2\n")
        with patch("tgcli.commands.remove.write_backup", side_effect=__import__("tgcli.backup", fromlist=["BackupError"]).BackupError("disk full")):
            result = run(file(tmp_path, GOOD), "--execute")
        assert result.exit_code == 1 and run.deletes == [] and "disk full" in result.output and "Nothing was removed" in result.output


class TestGuards:
    def test_any_blocked_line_means_nothing_is_removed(self, tmp_path):
        run = Run(tmp_path, answer="2\n")
        result = run(file(tmp_path, GOOD + "group,Okta Staff\n"), "--execute")
        assert result.exit_code == 1 and run.deletes == [] and "Nothing was removed: fix the file" in result.output
        assert "to confirm" not in result.output

    def test_an_incomplete_read_stops_an_execute(self, tmp_path):
        run = Run(tmp_path, problems=["groups: API reports 5, backed up 4"], answer="2\n")
        result = run(file(tmp_path, GOOD), "--execute")
        assert result.exit_code == 1 and run.deletes == [] and "Nothing was removed. Run it again" in result.output

    def test_a_read_error_removes_nothing(self, tmp_path):
        run = Run(tmp_path, answer="2\n")
        with patch("tgcli.commands.remove.collect", side_effect=__import__("tgcli.client.exceptions", fromlist=["x"]).TwingateAPIError("boom")):
            with patch("tgcli.commands._common.TwingateClient") as MockClient:
                MockClient.return_value.url = URL
                result = runner.invoke(app, ["-s", SESSION, "remove", str(file(tmp_path, GOOD)), "--execute"])
        assert result.exit_code == 1 and "boom" in result.output and run.deletes == []

    def test_a_bad_report_path_is_refused_before_anything_happens(self, tmp_path):
        run = Run(tmp_path, answer="2\n")
        result = run(file(tmp_path, GOOD), "--execute", report="no/such/dir/report.csv")
        assert result.exit_code == 1 and "cannot write the report" in result.output and run.reads == [] and run.deletes == []

    def test_a_file_that_cannot_be_read_is_refused(self, tmp_path):
        run = Run(tmp_path)
        result = run(tmp_path / "missing.csv")
        assert result.exit_code == 1 and "cannot read" in result.output and run.reads == []

    def test_a_network_whose_resources_are_not_all_listed_blocks_everything(self, tmp_path):
        run = Run(tmp_path, answer="2\n")
        result = run(file(tmp_path, "kind,name\nnetwork,DR\ngroup,Ops\n"), "--execute")
        assert result.exit_code == 1 and run.deletes == [] and "still in it would be left behind" in result.output


class TestFailures:
    def test_a_refused_delete_is_exit_1_and_the_rest_still_go(self, tmp_path):
        run = Run(tmp_path, answer="2\n", client=FakeClient(refuse=["R2"]))
        result = run(file(tmp_path, GOOD), "--execute", "--no-snapshot")
        assert result.exit_code == 1 and run.deletes == [("resourceDelete", "R2"), ("groupDelete", "G2")]
        assert "Removed 1 group; 1 failed." in result.output and "Run the same command again to finish" in result.output
        assert [(r["name"], r["status"]) for r in report_rows(tmp_path / "report.csv")] == [("Git", "error"), ("Ops", "removed")]

    def test_a_network_after_a_failed_resource_is_not_attempted(self, tmp_path):
        run = Run(tmp_path, answer="2\n", client=FakeClient(refuse=["R3"]))
        result = run(file(tmp_path, "kind,name,network\nnetwork,DR,\nresource,Docs,DR\n"), "--execute", "--no-snapshot")
        assert result.exit_code == 1 and run.deletes == [("resourceDelete", "R3")] and "not-run" in result.output

    def test_running_it_again_after_a_partial_run_finishes_the_job(self, tmp_path):
        items = world_items()
        items["resources"] = [r for r in items["resources"] if r["id"] != "R2"]  # R2 went the first time
        run = Run(tmp_path, items, answer="1\n")
        result = run(file(tmp_path, GOOD), "--execute", "--no-snapshot")
        assert result.exit_code == 0 and run.deletes == [("groupDelete", "G2")] and "1 not found" in result.output
