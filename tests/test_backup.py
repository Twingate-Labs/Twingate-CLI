"""Tests for the backup engine: collecting a tenant and writing it to disk."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from tgcli import backup
from tgcli.client.exceptions import TwingateAPIError
from tgcli.queries import backup as q

from .fake_tenant import FakeTenant, PAGE, edge, many

pytestmark = pytest.mark.filterwarnings("ignore")
NOW = datetime(2026, 10, 14, 15, 30, 0, tzinfo=timezone.utc)
ALL_NESTED = [(e.key, name) for e in q.ENTITIES for name in e.nested]


def ref(i: str) -> dict:
    return {"id": i, "name": f"n-{i}"}


def tenant_with_long_lists(n: int = 5) -> FakeTenant:
    """Every nested list holds n items, more than one page of PAGE."""
    users = [edge({"id": f"u{i}", "email": f"u{i}@x.io"}) for i in range(n)]
    refs = [edge(ref(f"r{i}")) for i in range(n)]
    access = [
        edge({"__typename": "Group" if i % 2 == 0 else "ServiceAccount", "id": f"p{i}", "name": f"P{i}"},
             securityPolicy=ref("sp"), accessPolicy={"mode": "MANUAL", "durationSeconds": None},
             approvalMode="MANUAL", expiresAt=None)
        for i in range(n)
    ]
    return FakeTenant({
        "groups": [{"id": "g1", "name": "G", "users": users, "resources": refs}],
        "users": [{"id": "u1", "email": "u1@x.io", "groups": refs}],
        "resources": [{"id": "res1", "name": "R", "__typename": "NetworkResource", "access": access, "approverGroups": refs}],
        "connectors": many("c", 1),
        "remote_networks": [{"id": "rn1", "name": "RN", "connectors": refs, "resources": refs, "gateways": [edge({"id": f"gw{i}", "address": f"a{i}"}) for i in range(n)]}],
    })


class TestCollect:
    def test_follows_top_level_pages_to_the_end(self):
        tenant = FakeTenant({"groups": [{"id": f"g{i}", "name": "x"} for i in range(5)], "users": many("u", 3)})
        collected = backup.collect(tenant)
        assert [g["id"] for g in collected.items["groups"]] == [f"g{i}" for i in range(5)]
        assert len(collected.items["users"]) == 3 and collected.problems == []

    def test_empty_tenant(self):
        collected = backup.collect(FakeTenant({}))
        assert all(items == [] for items in collected.items.values()) and collected.problems == []

    @pytest.mark.parametrize("entity,name", ALL_NESTED)
    def test_every_nested_list_is_completed_past_the_first_page(self, entity, name):
        collected = backup.collect(tenant_with_long_lists(5))
        item = collected.items[entity][0]
        assert len(item[name]) == 5 and collected.problems == []
        assert len(item[name]) > PAGE

    @pytest.mark.parametrize("entity,name", ALL_NESTED)
    def test_nested_lists_keep_api_order_without_duplicates(self, entity, name):
        collected = backup.collect(tenant_with_long_lists(7))
        item = collected.items[entity][0]
        ids = [x["principal"]["id"] if name == "access" else x["id"] for x in item[name]]
        assert len(ids) == len(set(ids)) == 7
        source = tenant_with_long_lists(7).data[entity][0][name]
        assert ids == [(e["node"]["id"]) for e in source]

    def test_short_nested_list_needs_no_extra_request(self):
        tenant = FakeTenant({"groups": [{"id": "g1", "name": "G", "users": [edge({"id": "u1", "email": "a@b"})], "resources": []}]})
        backup.collect(tenant)
        assert not any("(id: $id)" in query for query, _ in tenant.calls)

    def test_follow_up_queries_start_from_the_first_pages_cursor(self):
        tenant = tenant_with_long_lists(5)
        backup.collect(tenant)
        follow_ups = [v for query, v in tenant.calls if "(id: $id)" in query]
        assert follow_ups and all(v["cursor"] == f"c{PAGE}" for v in follow_ups[:1])

    def test_access_edges_are_flattened_with_principal_type_and_policy(self):
        collected = backup.collect(tenant_with_long_lists(3))
        first, second, _ = collected.items["resources"][0]["access"]
        assert first == {
            "principal": {"type": "Group", "id": "p0", "name": "P0"},
            "securityPolicy": ref("sp"), "accessPolicy": {"mode": "MANUAL", "durationSeconds": None},
            "approvalMode": "MANUAL", "expiresAt": None,
        }
        assert second["principal"]["type"] == "ServiceAccount"

    @pytest.mark.parametrize(
        "typename,label",
        [("NetworkResource", "NETWORK"), ("SSHResource", "SSH"), ("WebAppResource", "WEB_APP"),
         ("KubernetesResource", "KUBERNETES"), ("FutureResource", "FutureResource")],
    )
    def test_resources_get_a_type_label_instead_of_typename(self, typename, label):
        tenant = FakeTenant({"resources": [{"id": "r", "name": "R", "__typename": typename}]})
        resource = backup.collect(tenant).items["resources"][0]
        assert resource["type"] == label and "__typename" not in resource

    def test_top_level_count_mismatch_is_reported(self):
        tenant = FakeTenant({"users": many("u", 3)})
        tenant.total_override["users"] = 4
        problems = backup.collect(tenant).problems
        assert problems == ["users: API reports 4, backed up 3"]

    def test_nested_count_mismatch_is_reported_with_the_parent(self):
        tenant = tenant_with_long_lists(5)
        tenant.nested_total_override[("groups", "users")] = 6
        problems = backup.collect(tenant).problems
        assert problems == ["groups g1 users: API reports 6, backed up 5"]

    def test_parent_deleted_mid_backup_is_a_problem_not_a_crash(self):
        tenant = tenant_with_long_lists(5)
        tenant.vanished.add("g1")
        problems = backup.collect(tenant).problems
        assert any("g1" in p and "disappeared" in p for p in problems)

    def test_repeated_cursor_is_refused_instead_of_looping(self):
        tenant = FakeTenant({"users": many("u", 6)})
        tenant.stuck_cursor = True
        with pytest.raises(backup.BackupError, match="same page cursor"):
            backup.collect(tenant)

    def test_api_errors_propagate(self):
        tenant = FakeTenant({"users": many("u", 1)})
        tenant.error = TwingateAPIError("boom")
        with pytest.raises(TwingateAPIError):
            backup.collect(tenant)

    def test_progress_is_reported_per_entity(self):
        messages: list[str] = []
        backup.collect(FakeTenant({"users": many("u", 2)}), progress=messages.append)
        assert "Reading users..." in messages and "  2 users" in messages


def collected_sample() -> backup.Collected:
    return backup.collect(tenant_with_long_lists(3))


class TestWrite:
    def write(self, tmp_path, collected=None, name="out"):
        return backup.write_backup(collected or collected_sample(), tmp_path / name, session="s1", tenant="acme", now=NOW)

    def test_writes_one_file_per_entity_plus_manifest(self, tmp_path):
        result = self.write(tmp_path)
        assert sorted(p.name for p in result.path.iterdir()) == sorted(
            [e.file for e in q.ENTITIES] + [backup.MANIFEST_FILE]
        )
        assert result.counts == {"groups": 1, "users": 1, "resources": 1, "connectors": 1, "remote_networks": 1}
        assert not (tmp_path / "out.partial").exists()

    def test_files_hold_the_collected_data_as_json(self, tmp_path):
        collected = collected_sample()
        result = self.write(tmp_path, collected)
        assert json.loads((result.path / "groups.json").read_text()) == collected.items["groups"]
        assert json.loads((result.path / "remote-networks.json").read_text()) == collected.items["remote_networks"]

    def test_non_ascii_names_are_written_as_utf8_not_escaped(self, tmp_path):
        collected = backup.collect(FakeTenant({"users": [{"id": "u", "email": "j@x.io", "firstName": "José", "lastName": "Ñandú"}]}))
        result = self.write(tmp_path, collected)
        raw = (result.path / "users.json").read_bytes().decode("utf-8")
        assert "José" in raw and "\\u" not in raw

    def test_manifest_records_counts_checksums_and_context(self, tmp_path):
        result = self.write(tmp_path)
        manifest = json.loads((result.path / backup.MANIFEST_FILE).read_text())
        assert manifest["format"] == 1 and manifest["tenant"] == "acme" and manifest["session"] == "s1"
        assert manifest["createdAt"] == "2026-10-14T15:30:00+00:00"
        assert manifest["verification"] == {"complete": True, "problems": []}
        for entity in q.ENTITIES:
            data = (result.path / entity.file).read_bytes()
            assert manifest["files"][entity.file] == {"count": len(json.loads(data)), "sha256": hashlib.sha256(data).hexdigest()}
        assert any("Secrets are never included" in note for note in manifest["notes"])

    def test_problems_are_recorded_in_the_manifest(self, tmp_path):
        collected = collected_sample()
        collected.problems.append("users: API reports 4, backed up 3")
        result = self.write(tmp_path, collected)
        manifest = json.loads((result.path / backup.MANIFEST_FILE).read_text())
        assert manifest["verification"] == {"complete": False, "problems": ["users: API reports 4, backed up 3"]}
        assert result.problems == ["users: API reports 4, backed up 3"]

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
    def test_directory_and_files_are_private_to_the_owner(self, tmp_path):
        old = os.umask(0o000)
        try:
            result = self.write(tmp_path)
        finally:
            os.umask(old)
        assert stat.S_IMODE(result.path.stat().st_mode) == 0o700
        assert {stat.S_IMODE(p.stat().st_mode) for p in result.path.iterdir()} == {0o600}

    def test_existing_output_directory_is_refused_and_left_alone(self, tmp_path):
        (tmp_path / "out").mkdir()
        (tmp_path / "out" / "keep.txt").write_text("mine")
        with pytest.raises(backup.BackupError, match="already exists"):
            self.write(tmp_path)
        assert (tmp_path / "out" / "keep.txt").read_text() == "mine"

    def test_leftover_partial_directory_is_refused_and_left_alone(self, tmp_path):
        (tmp_path / "out.partial").mkdir()
        (tmp_path / "out.partial" / "keep.txt").write_text("mine")
        with pytest.raises(backup.BackupError, match="left over"):
            self.write(tmp_path)
        assert (tmp_path / "out.partial" / "keep.txt").read_text() == "mine"
        assert not (tmp_path / "out").exists()

    def test_missing_parent_directories_are_created(self, tmp_path):
        result = backup.write_backup(collected_sample(), tmp_path / "a" / "b" / "out", session="s", tenant="t", now=NOW)
        assert (result.path / "manifest.json").is_file()

    def test_failure_midway_leaves_neither_final_nor_partial_directory(self, tmp_path, monkeypatch):
        real, calls = backup._write_private, []

        def flaky(path, content):
            calls.append(path.name)
            if len(calls) == 3:
                raise OSError("disk full")
            real(path, content)

        monkeypatch.setattr(backup, "_write_private", flaky)
        with pytest.raises(OSError, match="disk full"):
            self.write(tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_interruption_also_cleans_up(self, tmp_path, monkeypatch):
        def interrupted(path, content):
            raise KeyboardInterrupt

        monkeypatch.setattr(backup, "_write_private", interrupted)
        with pytest.raises(KeyboardInterrupt):
            self.write(tmp_path)
        assert list(tmp_path.iterdir()) == []


class TestDefaultOutputPath:
    def test_names_the_tenant_and_a_utc_timestamp(self):
        client = SimpleNamespace(url="https://acme.twingate.com/api/graphql/")
        assert str(backup.default_output_path(client, NOW)) == "twingate-backup-acme-20261014T153000Z"

    def test_staging_hostnames_use_the_tenant_part(self):
        client = SimpleNamespace(url="https://acme.stg.opstg.com/api/graphql/")
        assert str(backup.default_output_path(client, NOW)) == "twingate-backup-acme-20261014T153000Z"

    def test_unknown_when_the_url_is_unusable(self):
        assert str(backup.default_output_path(SimpleNamespace(url=None), NOW)).startswith("twingate-backup-unknown-")
