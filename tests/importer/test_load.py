"""Reading import files: a backup's JSON and hand-written CSV give the same specs, and nothing is dropped silently."""

from __future__ import annotations

import json

import pytest

from tgcli.importer.load import LoadError, load, load_file, parse_ports


def write(path, text, encoding="utf-8"):
    path.write_text(text, encoding=encoding)
    return path


def dump(path, data):
    return write(path, json.dumps(data))


BACKUP_RESOURCE = {
    "type": "NETWORK", "id": "R1", "name": "Wiki", "alias": "wiki.corp", "isActive": True,
    "remoteNetwork": {"id": "N1", "name": "HQ"},
    "address": {"type": "DNS", "value": "wiki.internal"},
    "protocols": {"allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 80, "end": 80}, {"start": 8000, "end": 8100}]},
                  "udp": {"policy": "ALLOW_ALL", "ports": []}},
    "tags": [{"key": "env", "value": "prod"}], "isVisible": False, "isBrowserShortcutEnabled": True,
    "securityPolicy": {"id": "P1", "name": "Strict"}, "accessPolicy": {"mode": "AUTO_LOCK", "durationSeconds": 3600},
    "approvalMode": "AUTOMATIC", "approverGroups": [{"id": "G9", "name": "Approvers"}], "routingMode": "BYPASS_TWINGATE",
    "access": [
        {"principal": {"type": "Group", "id": "G1", "name": "Eng"}, "securityPolicy": {"id": "P2", "name": "Lax"},
         "accessPolicy": None, "approvalMode": None, "expiresAt": None},
        {"principal": {"type": "Group", "id": "G2", "name": "Ops"}, "securityPolicy": None,
         "accessPolicy": {"mode": "ACCESS_REQUEST", "durationSeconds": 60}, "approvalMode": "MANUAL", "expiresAt": "2999-01-01T00:00:00Z"},
        {"principal": {"type": "ServiceAccount", "id": "S1", "name": "ci"}, "securityPolicy": None},
        {"principal": {"type": "Group", "id": "G1", "name": "Eng"}, "securityPolicy": None},
    ],
}


class TestBackupJson:
    def test_a_backup_resource_is_read_in_full(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "resources.json", [BACKUP_RESOURCE]), "resources")
        assert (spec.name, spec.network, spec.address, spec.alias, spec.type) == ("Wiki", "HQ", "wiki.internal", "wiki.corp", "NETWORK")
        assert spec.protocols == {
            "allowIcmp": False,
            "tcp": {"policy": "RESTRICTED", "ports": [{"start": 80, "end": 80}, {"start": 8000, "end": 8100}]},
            "udp": {"policy": "ALLOW_ALL", "ports": []},
        }
        assert (spec.is_visible, spec.browser_shortcut, spec.routing_mode) == (False, True, "BYPASS_TWINGATE")
        assert spec.tags == [{"key": "env", "value": "prod"}]
        assert spec.security_policy == "Strict" and spec.problems == []
        assert spec.access_policy == {"mode": "AUTO_LOCK", "durationSeconds": 3600} and spec.approval_mode == "AUTOMATIC"

    def test_access_keeps_each_groups_own_settings_and_skips_repeats_and_service_accounts(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "resources.json", [BACKUP_RESOURCE]), "resources")
        assert [a.group for a in spec.access] == ["Eng", "Ops"]
        eng, ops = spec.access
        assert (eng.security_policy, eng.access_policy, eng.approval_mode, eng.expires_at) == ("Lax", None, None, None)
        assert (ops.security_policy, ops.access_policy, ops.approval_mode, ops.expires_at) == (
            None, {"mode": "ACCESS_REQUEST", "durationSeconds": 60}, "MANUAL", "2999-01-01T00:00:00Z")
        assert "access for service account 'ci' is not imported (only groups are)" in spec.notes
        assert "approver groups are not imported" in spec.notes

    def test_a_manual_access_policy_is_the_default_and_is_not_sent(self, tmp_path):
        record = {**BACKUP_RESOURCE, "accessPolicy": {"mode": "MANUAL", "durationSeconds": None}}
        (spec,) = load_file(dump(tmp_path / "resources.json", [record]), "resources")
        assert spec.access_policy is None

    def test_other_resource_types_are_kept_but_not_read(self, tmp_path):
        record = {"type": "SSH", "name": "bastion", "remoteNetwork": {"name": "HQ"}, "address": {"value": "10.0.0.1"}}
        (spec,) = load_file(dump(tmp_path / "resources.json", [record]), "resources")
        assert spec.type == "SSH" and spec.name == "bastion" and spec.problems == []

    def test_a_group_lists_members_by_email_without_repeats_ignoring_case(self, tmp_path):
        record = {"name": "Eng", "type": "MANUAL", "securityPolicy": {"id": "P", "name": "Strict"},
                  "users": [{"id": "U1", "email": "a@x.com"}, {"id": "U2", "email": "A@X.com"}, {"id": "U3", "email": "b@x.com"}]}
        (spec,) = load_file(dump(tmp_path / "groups.json", [record]), "groups")
        assert (spec.name, spec.type, spec.members, spec.security_policy) == ("Eng", "MANUAL", ["a@x.com", "b@x.com"], "Strict")

    def test_a_network_reads_its_settings(self, tmp_path):
        record = {"name": "HQ", "location": "ON_PREMISE", "networkType": "EXIT", "isActive": False}
        (spec,) = load_file(dump(tmp_path / "remote-networks.json", [record]), "remote-networks")
        assert (spec.name, spec.location, spec.network_type, spec.is_active) == ("HQ", "ON_PREMISE", "EXIT", False)

    def test_unicode_names_survive(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "groups.json", [{"name": "Ελληνικά 日本語", "users": []}]), "groups")
        assert spec.name == "Ελληνικά 日本語"

    @pytest.mark.parametrize("record,problem", [
        ({"location": "AWS"}, "has no name"),
        ({"name": "x", "location": "MARS"}, "location 'MARS' is not one of"),
        ({"name": "x", "networkType": "WEIRD"}, "network type 'WEIRD' is not one of"),
        ({"name": "x", "isActive": "maybe"}, "isActive 'maybe' is not true or false"),
    ])
    def test_a_bad_network_row_is_kept_with_its_problem(self, tmp_path, record, problem):
        (spec,) = load_file(dump(tmp_path / "remote-networks.json", [record]), "remote-networks")
        assert any(problem in p for p in spec.problems)

    @pytest.mark.parametrize("change,problem", [
        ({"address": None}, "has no address"),
        ({"remoteNetwork": None}, "has no Remote Network"),
        ({"name": ""}, "has no name"),
        ({"protocols": {"tcp": {"policy": "RESTRICTED", "ports": [{"start": 90, "end": 80}]}}}, "not valid"),
        ({"protocols": {"tcp": {"policy": "RESTRICTED", "ports": [{"start": 0, "end": 80}]}}}, "not valid"),
        ({"protocols": {"tcp": {"policy": "RESTRICTED", "ports": [{"start": 1, "end": 70000}]}}}, "not valid"),
        ({"protocols": {"tcp": {"policy": "ALLOW_ALL", "ports": [{"start": 80, "end": 80}]}}}, "ALLOW_ALL but also lists ports"),
        ({"protocols": {"tcp": {"policy": "SOMETIMES", "ports": []}}}, "tcp policy 'SOMETIMES'"),
        ({"routingMode": "SIDEWAYS"}, "routing mode 'SIDEWAYS'"),
        ({"approvalMode": "PERHAPS"}, "approval mode 'PERHAPS'"),
        ({"accessPolicy": {"mode": "NEVER"}}, "access policy mode 'NEVER'"),
    ])
    def test_a_bad_resource_row_is_kept_with_its_problem(self, tmp_path, change, problem):
        record = {**BACKUP_RESOURCE, **change}
        (spec,) = load_file(dump(tmp_path / "resources.json", [record]), "resources")
        assert any(problem in p for p in spec.problems), spec.problems

    def test_protocols_missing_from_a_resource_mean_everything_allowed(self, tmp_path):
        record = {"name": "x", "remoteNetwork": {"name": "HQ"}, "address": {"value": "a"}}
        (spec,) = load_file(dump(tmp_path / "resources.json", [record]), "resources")
        assert spec.protocols == {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}
        assert spec.is_visible is True and spec.browser_shortcut is False and spec.routing_mode is None


class TestEdgeCases:
    @pytest.mark.parametrize("word,expected", [("true", True), ("TRUE", True), ("yes", True), ("y", True), ("1", True),
                                               ("false", False), ("No", False), ("n", False), ("0", False)])
    def test_boolean_words(self, tmp_path, word, expected):
        f = write(tmp_path / "remote-networks.csv", f"name,active\nHQ,{word}\n")
        (spec,) = load_file(f, "remote-networks")
        assert spec.is_active is expected and spec.problems == []

    def test_a_port_range_without_an_end_is_a_problem(self, tmp_path):
        record = {**BACKUP_RESOURCE, "protocols": {"tcp": {"policy": "RESTRICTED", "ports": [{"start": 80}]}}}
        (spec,) = load_file(dump(tmp_path / "resources.json", [record]), "resources")
        assert any("needs a start and an end" in p for p in spec.problems)

    def test_a_group_without_a_name_is_a_problem(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "groups.json", [{"users": []}]), "groups")
        assert spec.problems == ["has no name"]

    def test_an_access_entry_without_a_group_name_is_a_problem_not_a_silent_drop(self, tmp_path):
        record = {**BACKUP_RESOURCE, "access": [{"principal": {"type": "Group", "id": "G1"}}]}
        (spec,) = load_file(dump(tmp_path / "resources.json", [record]), "resources")
        assert "an access entry has no group name" in spec.problems and spec.access == []


class TestCsv:
    def test_networks(self, tmp_path):
        f = write(tmp_path / "remote-networks.csv", "name,location,network_type,active\nHQ,on-premise,exit,no\nLab,,,\n")
        hq, lab = load_file(f, "remote-networks")
        assert (hq.name, hq.location, hq.network_type, hq.is_active, hq.problems) == ("HQ", "ON_PREMISE", "EXIT", False, [])
        assert (lab.location, lab.network_type, lab.is_active) == ("OTHER", "REGULAR", True)

    def test_an_abbreviated_location_is_a_problem_not_a_guess(self, tmp_path):
        (spec,) = load_file(write(tmp_path / "remote-networks.csv", "name,location\nHQ,on-prem\n"), "remote-networks")
        assert any("location 'on-prem' is not one of" in p for p in spec.problems)

    def test_groups_split_members_on_semicolons_or_commas_and_keep_the_policy(self, tmp_path):
        f = write(tmp_path / "groups.csv", 'name,members,security_policy\nEng,"a@x.com; b@x.com,c@x.com",Strict\nEmpty,,\n')
        eng, empty = load_file(f, "groups")
        assert eng.members == ["a@x.com", "b@x.com", "c@x.com"] and eng.security_policy == "Strict"
        assert empty.members == [] and empty.security_policy is None

    def test_resources_with_ports_visibility_and_per_group_policies(self, tmp_path):
        f = write(tmp_path / "resources.csv",
                  "name,network,address,alias,tcp_ports,udp_ports,allow_icmp,visible,security_policy,groups,routing_mode\n"
                  'Wiki,HQ,wiki.internal,wiki.corp,80;443;8000-8100,none,false,no,Strict,"Eng=Lax;Ops, EMEA;Dev",bypass-twingate\n')
        (spec,) = load_file(f, "resources")
        assert spec.problems == []
        assert spec.protocols == {
            "allowIcmp": False,
            "tcp": {"policy": "RESTRICTED", "ports": [{"start": 80, "end": 80}, {"start": 443, "end": 443}, {"start": 8000, "end": 8100}]},
            "udp": {"policy": "RESTRICTED", "ports": []},
        }
        assert (spec.is_visible, spec.security_policy, spec.routing_mode) == (False, "Strict", "BYPASS_TWINGATE")
        assert [(a.group, a.security_policy) for a in spec.access] == [("Eng", "Lax"), ("Ops, EMEA", None), ("Dev", None)]

    def test_blank_ports_and_flags_mean_everything_allowed_and_visible(self, tmp_path):
        f = write(tmp_path / "resources.csv", "name,network,address\nWiki,HQ,wiki.internal\n")
        (spec,) = load_file(f, "resources")
        assert spec.protocols == {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}
        assert spec.is_visible is True and spec.access == []

    def test_headers_are_case_and_space_insensitive_and_a_bom_is_ignored(self, tmp_path):
        f = write(tmp_path / "groups.csv", "﻿ Name , Members \nEng,a@x.com\n", encoding="utf-8")
        (spec,) = load_file(f, "groups")
        assert spec.name == "Eng" and spec.members == ["a@x.com"]

    def test_row_numbers_count_the_header_as_a_spreadsheet_does(self, tmp_path):
        f = write(tmp_path / "groups.csv", "name\nA\nB\n")
        assert [s.source for s in load_file(f, "groups")] == ["groups.csv row 2", "groups.csv row 3"]

    def test_json_items_are_numbered_from_one(self, tmp_path):
        f = dump(tmp_path / "groups.json", [{"name": "A"}, {"name": "B"}])
        assert [s.source for s in load_file(f, "groups")] == ["groups.json item 1", "groups.json item 2"]

    @pytest.mark.parametrize("text,problem", [
        ("name,network,address,tcp_ports\nW,HQ,a,80-x\n", "tcp_ports '80-x' is not a port"),
        ("name,network,address,tcp_ports\nW,HQ,a,0\n", "not a valid port range"),
        ("name,network,address,tcp_ports\nW,HQ,a,90-80\n", "not a valid port range"),
        ("name,network,address,tcp_ports\nW,HQ,a,70000\n", "not a valid port range"),
        ("name,network,address,visible\nW,HQ,a,sometimes\n", "isVisible 'sometimes' is not true or false"),
        ("name,network,address,allow_icmp\nW,HQ,a,2\n", "allowIcmp '2' is not true or false"),
        ("name,network,address\n,HQ,a\n", "has no name"),
        ("name,network,address\nW,,a\n", "has no Remote Network"),
        ("name,network,address\nW,HQ,\n", "has no address"),
    ])
    def test_a_bad_resource_row_is_kept_with_its_problem(self, tmp_path, text, problem):
        (spec,) = load_file(write(tmp_path / "resources.csv", text), "resources")
        assert any(problem in p for p in spec.problems), spec.problems

    def test_an_unknown_column_stops_the_load_so_a_typo_cannot_silently_drop_access(self, tmp_path):
        f = write(tmp_path / "resources.csv", "name,network,address,group\nW,HQ,a,Eng\n")
        with pytest.raises(LoadError, match="column.*group.*Columns for resources"):
            load_file(f, "resources")

    def test_a_missing_required_column_stops_the_load(self, tmp_path):
        with pytest.raises(LoadError, match="missing the required column.*network"):
            load_file(write(tmp_path / "resources.csv", "name,address\nW,a\n"), "resources")

    def test_a_header_only_file_has_no_rows(self, tmp_path):
        assert load_file(write(tmp_path / "groups.csv", "name,members\n"), "groups") == []

    @pytest.mark.parametrize("text,expected", [
        ("", ("ALLOW_ALL", [])), ("*", ("ALLOW_ALL", [])), ("all", ("ALLOW_ALL", [])), ("ALL", ("ALLOW_ALL", [])),
        ("none", ("RESTRICTED", [])), ("None", ("RESTRICTED", [])),
        ("443", ("RESTRICTED", [{"start": 443, "end": 443}])),
        ("1-65535", ("RESTRICTED", [{"start": 1, "end": 65535}])),
        (" 22 ; 80 , 8000 - 8100 ", ("RESTRICTED", [{"start": 22, "end": 22}, {"start": 80, "end": 80}, {"start": 8000, "end": 8100}])),
    ])
    def test_port_lists(self, text, expected):
        problems: list = []
        result = parse_ports(text, "tcp_ports", problems)
        assert (result["policy"], result["ports"]) == expected and problems == []


class TestFolders:
    def test_a_folder_reads_each_kind_it_has_and_lists_unused_backup_files(self, tmp_path):
        dump(tmp_path / "groups.json", [{"name": "Eng"}])
        write(tmp_path / "remote-networks.csv", "name\nHQ\n")
        dump(tmp_path / "users.json", [])
        dump(tmp_path / "manifest.json", {})
        specs = load(tmp_path)
        assert [g.name for g in specs.groups] == ["Eng"] and [n.name for n in specs.networks] == ["HQ"] and specs.resources == []
        assert specs.files == ["remote-networks.csv", "groups.json"] and specs.ignored == ["users.json", "manifest.json"]

    def test_one_file_is_read_by_its_name(self, tmp_path):
        specs = load(dump(tmp_path / "groups.json", [{"name": "Eng"}]))
        assert [g.name for g in specs.groups] == ["Eng"] and specs.networks == [] and specs.ignored == []

    @pytest.mark.parametrize("setup,message", [
        (lambda p: None, "has none of"),
        (lambda p: (dump(p / "groups.json", []), write(p / "groups.csv", "name\n")), "both groups.json and groups.csv"),
        (lambda p: write(p / "groups.json", "{not json"), "is not valid JSON"),
        (lambda p: write(p / "groups.json", '{"a": 1}'), "must hold a JSON list"),
        (lambda p: write(p / "groups.json", '["x"]'), "item 1 is not an object"),
        (lambda p: (p / "groups.json").write_bytes(b"\xc3\x28 bad"), "Cannot read"),
        (lambda p: (p / "groups.csv").write_bytes(b"name\n\xff\xfe\n"), "Cannot read"),
    ])
    def test_unreadable_input_is_an_error_not_a_silent_skip(self, tmp_path, setup, message):
        setup(tmp_path)
        with pytest.raises(LoadError, match=message):
            load(tmp_path)

    def test_a_file_that_is_not_named_for_what_it_holds(self, tmp_path):
        with pytest.raises(LoadError, match="Cannot tell what stuff.json holds"):
            load(dump(tmp_path / "stuff.json", []))

    def test_a_path_that_does_not_exist(self, tmp_path):
        with pytest.raises(LoadError, match="does not exist"):
            load(tmp_path / "nope")
