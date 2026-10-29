"""Tests for the backup command."""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

from ..fake_tenant import FakeTenant, edge, many

runner = CliRunner()
SESSION = "TestSess"
URL = "https://acme.twingate.com/api/graphql/"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def tenant() -> FakeTenant:
    return FakeTenant({
        "groups": [{"id": f"g{i}", "name": f"G{i}", "users": [edge({"id": f"u{j}", "email": f"u{j}@x.io"}) for j in range(5)]} for i in range(3)],
        "users": many("u", 4),
        "resources": [{"id": "r1", "name": "R", "__typename": "SSHResource"}],
        "connectors": many("c", 2),
        "remote_networks": many("rn", 5),
        "devices": many("d", 6),
        "service_accounts": many("sa", 2),
        "security_policies": many("sp", 3),
        "dns_profiles": many("dp", 1),
        "gateways": many("gw", 1),
        "certificate_authorities": [{"id": "ca1", "name": "CA", "__typename": "X509CertificateAuthority"}],
    })


def invoke(fake: FakeTenant, *args: str):
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        inst = MockClient.return_value
        inst.url = URL
        inst.execute.side_effect = fake.execute
        return runner.invoke(app, ["-s", SESSION, *args])


class TestBackupCommand:
    def test_writes_the_backup_and_reports_counts(self, tmp_path):
        out = tmp_path / "bk"
        result = invoke(tenant(), "backup", "-o", str(out))
        assert result.exit_code == 0, result.output
        assert f"Backup written to {out}" in result.output
        for label, count in [
            ("groups", 3), ("users", 4), ("resources", 1), ("connectors", 2), ("remote networks", 5), ("devices", 6),
            ("service accounts", 2), ("security policies", 3), ("DNS profiles", 1), ("gateways", 1),
            ("certificate authorities", 1),
        ]:
            assert re.search(rf"{label}\s+{count}\b", result.output), label
        assert "Verified: every count matches the API." in result.output
        assert len(json.loads((out / "groups.json").read_text())[0]["users"]) == 5
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest["tenant"] == "acme" and manifest["session"] == SESSION and manifest["verification"]["complete"]

    def test_default_output_directory_is_named_after_the_tenant(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = invoke(tenant(), "backup")
        assert result.exit_code == 0, result.output
        (created,) = list(tmp_path.iterdir())
        assert re.fullmatch(r"twingate-backup-acme-\d{8}T\d{6}Z", created.name)
        assert (created / "manifest.json").is_file()

    def test_progress_goes_to_the_error_stream_and_summary_to_stdout(self, tmp_path):
        out = tmp_path / "bk"
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.url = URL
            inst.execute.side_effect = tenant().execute
            result = runner.invoke(app, ["-s", SESSION, "backup", "-o", str(out)])
        assert "Reading groups..." in result.stderr and "Reading groups" not in result.stdout
        assert "Backup written to" in result.stdout

    def test_existing_output_directory_is_refused(self, tmp_path):
        (tmp_path / "bk").mkdir()
        result = invoke(tenant(), "backup", "-o", str(tmp_path / "bk"))
        assert result.exit_code == 1 and "already exists" in result.output
        assert list((tmp_path / "bk").iterdir()) == []

    def test_api_error_midway_exits_nonzero_and_leaves_nothing_behind(self, tmp_path):
        fake = tenant()
        fake.error, fake.fail_after = TwingateAPIError("server on fire"), 3
        result = invoke(fake, "backup", "-o", str(tmp_path / "bk"))
        assert result.exit_code == 1 and "API error: server on fire" in result.output
        assert list(tmp_path.iterdir()) == []

    def test_auth_error_exits_nonzero(self, tmp_path):
        fake = tenant()
        fake.error = TwingateAuthError("Bad token")
        result = invoke(fake, "backup", "-o", str(tmp_path / "bk"))
        assert result.exit_code == 1 and "Authentication error" in result.output
        assert list(tmp_path.iterdir()) == []

    def test_unverifiable_backup_is_still_written_but_exits_nonzero(self, tmp_path):
        fake = tenant()
        fake.total_override["users"] = 9
        result = invoke(fake, "backup", "-o", str(tmp_path / "bk"))
        assert result.exit_code == 1
        assert "could not be fully verified" in result.output and "users: API reports 9, backed up 4" in result.output
        assert "Verified: every count" not in result.output
        manifest = json.loads((tmp_path / "bk" / "manifest.json").read_text())
        assert manifest["verification"]["complete"] is False and manifest["verification"]["problems"]

    def test_long_problem_lists_are_truncated_on_screen_but_complete_in_the_manifest(self, tmp_path):
        fake = FakeTenant({"groups": [{"id": f"g{i}", "name": "x", "users": [edge({"id": "u", "email": "e"})]} for i in range(15)]})
        fake.nested_total_override[("groups", "users")] = 2  # applies to every group: 15 mismatches
        result = invoke(fake, "backup", "-o", str(tmp_path / "bk"))
        assert result.exit_code == 1 and "and 5 more (see manifest.json)" in result.output
        assert len(json.loads((tmp_path / "bk" / "manifest.json").read_text())["verification"]["problems"]) == 15

    def test_no_session_exits_nonzero(self, tmp_path):
        result = runner.invoke(app, ["backup", "-o", str(tmp_path / "bk")])
        assert result.exit_code != 0 and not (tmp_path / "bk").exists()

    def test_output_flag_has_a_short_form(self, tmp_path):
        result = invoke(tenant(), "backup", "--output", str(tmp_path / "long"))
        assert result.exit_code == 0 and (tmp_path / "long").is_dir()


class TestTypeTheApiRefuses:
    def refusing(self):
        fake = tenant()
        real = fake.execute

        def execute(query, variables=None):
            if "securityPolicies(after" in query:
                raise TwingateAPIError("no access to security policies")
            return real(query, variables)

        fake.execute = execute
        return fake

    def test_the_rest_is_written_and_the_gap_is_named_but_it_exits_nonzero(self, tmp_path):
        out = tmp_path / "bk"
        result = invoke(self.refusing(), "backup", "-o", str(out))
        assert result.exit_code == 1, result.output
        assert re.search(r"security policies\s+NOT READ", result.output)
        assert re.search(r"devices\s+6\b", result.output)
        assert "no access to security policies" in result.output and "could not be fully verified" in result.output
        assert (out / "devices.json").is_file() and not (out / "security-policies.json").exists()
        assert "Verified: every count" not in result.output
