"""Tests for `tgcli backup diff`: comparing two backup folders."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli import backup
from tgcli.backup_diff import DiffError, compare, load_backup, render, to_dict
from tgcli.main import app
from tgcli.queries import backup as q

runner = CliRunner()
T0 = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc)


def ref(i, name):
    return {"id": i, "name": name}


def base_items():
    return {
        "groups": [
            {"id": "g1", "name": "Eng", "type": "MANUAL", "updatedAt": "t1", "securityPolicy": ref("sp1", "Default"),
             "users": [{"id": "u1", "email": "a@x.io"}, {"id": "u2", "email": "b@x.io"}], "resources": [ref("r1", "Wiki")]},
            {"id": "g2", "name": "Ops", "type": "MANUAL", "securityPolicy": None, "users": [], "resources": []},
        ],
        "users": [{"id": "u1", "email": "a@x.io", "role": "ADMIN", "groups": [ref("g1", "Eng")]}],
        "resources": [{
            "id": "r1", "name": "Wiki", "type": "NETWORK", "isVisible": True, "securityPolicy": ref("sp1", "Default"),
            "tags": [{"key": "env", "value": "prod"}],
            "protocols": {"allowIcmp": True, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}]}, "udp": {"policy": "ALLOW_ALL", "ports": []}},
            "access": [
                {"principal": {"type": "Group", "id": "g1", "name": "Eng"}, "securityPolicy": None, "accessPolicy": {"mode": "MANUAL", "durationSeconds": None}, "approvalMode": "MANUAL", "expiresAt": None},
            ],
            "approverGroups": [],
        }],
        "connectors": [{"id": "c1", "name": "conn", "state": "ONLINE", "version": "1.0", "lastHeartbeatAt": "h1"}],
        "remote_networks": [{"id": "rn1", "name": "HQ", "location": "AWS"}],
        "devices": [{"id": "d1", "name": "Laptop", "isTrusted": True, "lastSuccessfulLoginAt": "l1", "serialNumber": "S1"}],
        "service_accounts": [{"id": "sa1", "name": "ci", "resources": [], "keys": [{"id": "k1", "name": "key", "status": "ACTIVE", "expiresAt": None, "updatedAt": "k"}]}],
        "security_policies": [{"id": "sp1", "name": "Default", "policyType": "DEFAULT_RESOURCE", "groups": [ref("g1", "Eng")]}],
        "dns_profiles": [{"id": "dp1", "name": "Strict", "allowedDomains": ["a.com", "b.com"], "deniedDomains": [], "groups": []}],
        "gateways": [], "certificate_authorities": [],
    }


def write(tmp_path, name, items=None, tenant="acme", when=T0, problems=None, drop=()):
    items = base_items() if items is None else items
    collected = backup.Collected(items={e.key: copy.deepcopy(items.get(e.key, [])) for e in q.ENTITIES}, problems=list(problems or []))
    path = backup.write_backup(collected, tmp_path / name, session="s", tenant=tenant, now=when).path
    for key in drop:
        file = next(e.file for e in q.ENTITIES if e.key == key)
        (path / file).unlink()
    return path


def edited(mutate):
    items = base_items()
    mutate(items)
    return items


def diff(tmp_path, mutate, **kwargs):
    old = write(tmp_path, "old")
    new = write(tmp_path, "new", edited(mutate), when=T0 + timedelta(days=7))
    return compare(load_backup(old), load_backup(new), **kwargs)


def changes_of(result, key, name=None):
    (entry,) = [t for t in result.types if t.key == key]
    objects = entry.changed if name is None else [o for o in entry.changed if o.label == name]
    return {(c.kind, c.path, c.old, c.new) for o in objects for c in o.changes}


class TestObjects:
    def test_identical_backups_have_no_differences(self, tmp_path):
        result = compare(load_backup(write(tmp_path, "a")), load_backup(write(tmp_path, "b")))
        assert result.differences == 0 and render(result).endswith("No differences.")

    def test_added_removed_and_renamed_objects_are_matched_by_id(self, tmp_path):
        def mutate(items):
            items["groups"].append({"id": "g3", "name": "New", "users": [], "resources": []})
            del items["groups"][1]
            items["groups"][0]["name"] = "Engineering"
        (entry,) = [t for t in diff(tmp_path, mutate).types if t.key == "groups"]
        assert [o.label for o in entry.added] == ["New"] and [o.label for o in entry.removed] == ["Ops"]
        assert [o.label for o in entry.changed] == ["Engineering"]
        assert ("changed", "name", "Eng", "Engineering") in {(c.kind, c.path, c.old, c.new) for c in entry.changed[0].changes}

    def test_an_object_is_not_confused_with_another_that_has_the_same_name(self, tmp_path):
        def mutate(items):
            items["groups"][1]["id"], items["groups"][1]["name"] = "g9", "Eng"
        (entry,) = [t for t in diff(tmp_path, mutate).types if t.key == "groups"]
        assert [o.id for o in entry.added] == ["g9"] and [o.id for o in entry.removed] == ["g2"]

    def test_names_that_repeat_are_shown_with_their_ids(self, tmp_path):
        def mutate(items):
            items["groups"].append({"id": "g8", "name": "Eng", "users": [], "resources": []})
        text = render(diff(tmp_path, mutate))
        assert "+ Eng  (g8)" in text

    def test_non_ascii_names_survive(self, tmp_path):
        def mutate(items):
            items["groups"][0]["name"] = "Ελληνικά 😀"
        assert "~ name: Eng -> Ελληνικά 😀" in render(diff(tmp_path, mutate))


class TestNestedLists:
    def test_reordering_a_list_is_not_a_change(self, tmp_path):
        def mutate(items):
            items["groups"][0]["users"].reverse()
            items["dns_profiles"][0]["allowedDomains"].reverse()
        assert diff(tmp_path, mutate).differences == 0

    def test_members_added_and_removed(self, tmp_path):
        def mutate(items):
            items["groups"][0]["users"] = [{"id": "u1", "email": "a@x.io"}, {"id": "u3", "email": "c@x.io"}]
        assert changes_of(diff(tmp_path, mutate), "groups") == {("added", "users", "", "c@x.io"), ("removed", "users", "b@x.io", "")}

    def test_a_changed_access_setting_is_reported_on_the_grant_it_belongs_to(self, tmp_path):
        def mutate(items):
            items["resources"][0]["access"][0]["approvalMode"] = "AUTOMATIC"
            items["resources"][0]["access"][0]["accessPolicy"] = {"mode": "AUTO_LOCK", "durationSeconds": 604800}
        assert changes_of(diff(tmp_path, mutate), "resources") == {
            ("changed", "access[Eng].approvalMode", "MANUAL", "AUTOMATIC"),
            ("changed", "access[Eng].accessPolicy.mode", "MANUAL", "AUTO_LOCK"),
            ("changed", "access[Eng].accessPolicy.durationSeconds", "none", "604800"),
        }

    def test_a_grant_added_or_removed(self, tmp_path):
        def mutate(items):
            items["resources"][0]["access"].append({"principal": {"type": "ServiceAccount", "id": "sa1", "name": "ci"}, "securityPolicy": None})
        assert changes_of(diff(tmp_path, mutate), "resources") == {("added", "access", "", "ci")}

    def test_tags_are_matched_by_key(self, tmp_path):
        def mutate(items):
            items["resources"][0]["tags"] = [{"key": "env", "value": "dev"}, {"key": "team", "value": "x"}]
        assert changes_of(diff(tmp_path, mutate), "resources") == {("added", "tags", "", "team=x"), ("changed", "tags[env].value", "prod", "dev")}

    def test_ports_have_no_id_and_are_compared_as_a_set(self, tmp_path):
        def mutate(items):
            items["resources"][0]["protocols"]["tcp"]["ports"] = [{"start": 443, "end": 443}, {"start": 8080, "end": 8090}]
        assert changes_of(diff(tmp_path, mutate), "resources") == {("added", "protocols.tcp.ports", "", "8080-8090")}

    def test_plain_string_lists_are_compared_as_sets(self, tmp_path):
        def mutate(items):
            items["dns_profiles"][0]["allowedDomains"] = ["b.com", "c.com"]
        assert changes_of(diff(tmp_path, mutate), "dns_profiles") == {("added", "allowedDomains", "", "c.com"), ("removed", "allowedDomains", "a.com", "")}

    def test_a_list_that_repeats_an_id_falls_back_to_a_set_instead_of_losing_one(self, tmp_path):
        def mutate(items):
            items["groups"][0]["users"] = [{"id": "u1", "email": "a@x.io"}, {"id": "u1", "email": "a@x.io"}, {"id": "u2", "email": "z@x.io"}]
        assert changes_of(diff(tmp_path, mutate), "groups") == {("added", "users", "", "z@x.io"), ("removed", "users", "b@x.io", "")}

    def test_key_metadata_changes_are_found_inside_a_service_account(self, tmp_path):
        def mutate(items):
            items["service_accounts"][0]["keys"][0]["status"] = "REVOKED"
        assert changes_of(diff(tmp_path, mutate), "service_accounts") == {("changed", "keys[key].status", "ACTIVE", "REVOKED")}


class TestValues:
    def test_a_replaced_reference_is_one_change_naming_both(self, tmp_path):
        def mutate(items):
            items["groups"][0]["securityPolicy"] = ref("sp2", "Strict")
        assert changes_of(diff(tmp_path, mutate), "groups") == {("changed", "securityPolicy", "Default", "Strict")}

    def test_a_renamed_reference_is_a_change_to_its_name(self, tmp_path):
        def mutate(items):
            items["groups"][0]["securityPolicy"] = ref("sp1", "Renamed")
        assert changes_of(diff(tmp_path, mutate), "groups") == {("changed", "securityPolicy.name", "Default", "Renamed")}

    def test_none_to_a_value_and_back(self, tmp_path):
        def mutate(items):
            items["groups"][1]["securityPolicy"] = ref("sp1", "Default")
        assert changes_of(diff(tmp_path, mutate), "groups") == {("changed", "securityPolicy", "none", "Default")}

    def test_booleans_read_as_true_and_false(self, tmp_path):
        def mutate(items):
            items["resources"][0]["isVisible"] = False
        assert changes_of(diff(tmp_path, mutate), "resources") == {("changed", "isVisible", "true", "false")}

    def test_a_field_that_appears_or_disappears(self, tmp_path):
        def mutate(items):
            items["remote_networks"][0]["networkType"] = "REGULAR"
            del items["remote_networks"][0]["location"]
        assert changes_of(diff(tmp_path, mutate), "remote_networks") == {("changed", "networkType", "none", "REGULAR"), ("changed", "location", "AWS", "none")}


class TestVolatileFields:
    @staticmethod
    def churn(items):
        items["connectors"][0]["lastHeartbeatAt"] = "h2"
        items["devices"][0]["lastSuccessfulLoginAt"] = "l2"
        items["groups"][0]["updatedAt"] = "t2"
        items["service_accounts"][0]["keys"][0]["updatedAt"] = "k2"

    def test_fields_that_change_on_their_own_are_ignored(self, tmp_path):
        assert diff(tmp_path, self.churn).differences == 0

    def test_a_real_change_next_to_them_is_still_found(self, tmp_path):
        def mutate(items):
            self.churn(items)
            items["connectors"][0]["state"] = "OFFLINE"
        assert changes_of(diff(tmp_path, mutate), "connectors") == {("changed", "state", "ONLINE", "OFFLINE")}

    def test_include_volatile_compares_them(self, tmp_path):
        result = diff(tmp_path, self.churn, include_volatile=True)
        assert result.differences == 4
        assert changes_of(result, "connectors") == {("changed", "lastHeartbeatAt", "h1", "h2")}
        assert changes_of(result, "service_accounts") == {("changed", "keys[key].updatedAt", "k", "k2")}


class TestLoading:
    def test_different_tenants_are_refused(self, tmp_path):
        with pytest.raises(DiffError, match="different tenants"):
            compare(load_backup(write(tmp_path, "a", tenant="acme")), load_backup(write(tmp_path, "b", tenant="other")))

    def test_a_folder_without_a_manifest_is_not_a_backup(self, tmp_path):
        (tmp_path / "x").mkdir()
        with pytest.raises(DiffError, match="not a `tgcli backup` folder"):
            load_backup(tmp_path / "x")

    def test_a_file_or_missing_path_is_not_a_backup(self, tmp_path):
        (tmp_path / "f").write_text("x")
        for path in (tmp_path / "f", tmp_path / "nope"):
            with pytest.raises(DiffError, match="is not a folder"):
                load_backup(path)

    def test_an_unknown_manifest_format_is_refused(self, tmp_path):
        path = write(tmp_path, "a")
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["format"] = 99
        (path / "manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(DiffError, match="format 1"):
            load_backup(path)

    @pytest.mark.parametrize("content,message", [("{not json", "not valid JSON"), ('{"a": 1}', "must hold a list"), ('[1]', "must hold a list")])
    def test_a_damaged_data_file_is_an_error(self, tmp_path, content, message):
        path = write(tmp_path, "a")
        (path / "groups.json").write_text(content)
        with pytest.raises(DiffError, match=message):
            load_backup(path)

    def test_a_file_changed_after_the_backup_gets_a_warning(self, tmp_path):
        path = write(tmp_path, "a")
        (path / "groups.json").write_text("[]")
        assert any("does not match the checksum" in w for w in load_backup(path).warnings)

    def test_a_backup_that_was_not_fully_verified_gets_a_warning(self, tmp_path):
        result = compare(load_backup(write(tmp_path, "a", problems=["users: API reports 4, backed up 3"])), load_backup(write(tmp_path, "b")))
        assert any("not fully verified" in w for w in result.warnings)

    def test_giving_the_backups_the_wrong_way_round_is_noted(self, tmp_path):
        result = compare(load_backup(write(tmp_path, "a", when=T0 + timedelta(days=1))), load_backup(write(tmp_path, "b")))
        assert any("newer than the second" in w for w in result.warnings)

    def test_a_type_only_one_backup_has_is_named_not_compared(self, tmp_path):
        old, new = write(tmp_path, "old", drop=("devices", "gateways")), write(tmp_path, "new")
        result = compare(load_backup(old), load_backup(new))
        assert result.not_compared == ["devices (only in the second backup)", "gateways (only in the second backup)"]
        assert "devices" not in [t.key for t in result.types] and "Not compared: devices" in render(result)
        assert result.differences == 0
        assert compare(load_backup(new), load_backup(old)).not_compared[0] == "devices (only in the first backup)"

    def test_a_utf8_byte_order_mark_is_tolerated(self, tmp_path):
        path = write(tmp_path, "a")
        raw = (path / "groups.json").read_bytes()
        (path / "groups.json").write_bytes(b"\xef\xbb\xbf" + raw)
        assert load_backup(path).items["groups"][0]["name"] == "Eng"


class TestOutput:
    def test_the_text_report(self, tmp_path):
        def mutate(items):
            items["groups"][0]["users"].pop()
            items["groups"].append({"id": "g3", "name": "New", "users": [], "resources": []})
        text = render(diff(tmp_path, mutate))
        assert "Comparing backups of acme" in text
        assert "groups: 1 added, 0 removed, 1 changed" in text
        assert "  + New" in text and "  ~ Eng" in text and "      - users: b@x.io" in text
        assert "1 object(s)" not in text and "2 object(s) differ, in 1 type(s)." in text
        assert "users:" not in text.split("groups:")[0]  # untouched types are not listed

    def test_the_json_report(self, tmp_path):
        def mutate(items):
            items["groups"][0]["name"] = "Eng2"
        data = to_dict(diff(tmp_path, mutate))
        assert data["tenant"] == "acme" and data["differences"] == 1 and data["notCompared"] == []
        assert data["types"]["groups"]["changed"] == [
            {"id": "g1", "name": "Eng2", "changes": [{"kind": "changed", "path": "name", "old": "Eng", "new": "Eng2"}]}
        ]
        assert set(data["types"]) == {e.key for e in q.ENTITIES}


class TestCommand:
    @staticmethod
    def run(tmp_path, mutate=None, *flags):
        work = tmp_path / f"run{len(list(tmp_path.iterdir()))}"  # a test may run the command more than once
        work.mkdir()
        old = write(work, "old")
        new = write(work, "new", edited(mutate) if mutate else None, when=T0 + timedelta(days=1))
        with patch("tgcli.commands._common.TwingateClient", side_effect=AssertionError("diff must not talk to the API")):
            return runner.invoke(app, ["backup", "diff", str(old), str(new), *flags])

    @staticmethod
    def rename(items):
        items["groups"][0]["name"] = "Eng2"

    def test_it_needs_no_session_and_makes_no_api_calls(self, tmp_path):
        result = self.run(tmp_path, self.rename)
        assert result.exit_code == 0, result.output
        assert "~ Eng2" in result.output and "name: Eng -> Eng2" in result.output

    def test_differences_exit_0_by_default_and_1_with_exit_code(self, tmp_path):
        assert self.run(tmp_path, self.rename).exit_code == 0
        assert self.run(tmp_path, self.rename, "--exit-code").exit_code == 1

    def test_no_differences_exit_0_even_with_exit_code(self, tmp_path):
        result = self.run(tmp_path, None, "--exit-code")
        assert result.exit_code == 0 and "No differences." in result.output

    def test_json_flag(self, tmp_path):
        result = self.run(tmp_path, self.rename, "--json")
        assert json.loads(result.stdout)["differences"] == 1

    def test_include_volatile_flag(self, tmp_path):
        def churn(items):
            items["groups"][0]["updatedAt"] = "later"
        assert "No differences." in self.run(tmp_path, churn).output
        assert "updatedAt" in self.run(tmp_path, churn, "--include-volatile").output

    def test_a_bad_folder_exits_2_with_the_reason_on_stderr(self, tmp_path):
        result = runner.invoke(app, ["backup", "diff", str(tmp_path / "nope"), str(tmp_path / "nada")])
        assert result.exit_code == 2 and "is not a folder" in result.stderr and result.stdout == ""

    def test_different_tenants_exit_2(self, tmp_path):
        a, b = write(tmp_path, "a", tenant="acme"), write(tmp_path, "b", tenant="other")
        result = runner.invoke(app, ["backup", "diff", str(a), str(b)])
        assert result.exit_code == 2 and "different tenants" in result.stderr

    def test_warnings_go_to_stderr_and_the_report_to_stdout(self, tmp_path):
        a, b = write(tmp_path, "a", problems=["x"]), write(tmp_path, "b")
        result = runner.invoke(app, ["backup", "diff", str(a), str(b), "--json"])
        assert "Warning:" in result.stderr and "Warning" not in result.stdout
        json.loads(result.stdout)

    def test_the_plain_backup_command_still_runs_a_backup(self):
        result = runner.invoke(app, ["backup", "--help"])
        assert result.exit_code == 0 and "--output" in result.output and "diff" in result.output

    def test_it_is_listed_in_help(self):
        assert "first" in runner.invoke(app, ["backup", "diff", "--help"]).output.lower()
