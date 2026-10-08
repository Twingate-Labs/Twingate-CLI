"""Tests for ca (certificate authority) commands."""

from __future__ import annotations

import csv
import io
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
X509 = {"__typename": "X509CertificateAuthority", "id": "x-1", "name": "Corp X509", "fingerprint": "AA:BB"}
SSH = {"__typename": "SSHCertificateAuthority", "id": "s-1", "name": "Vault SSH CA", "fingerprint": "SHA256:xyz"}


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def _rows(output):
    return list(csv.DictReader(io.StringIO(output)))


class TestRead:
    def test_list_labels_types_across_pages(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[{"node": X509}], [{"node": SSH}]]
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "ca", "list"])
        assert result.exit_code == 0
        rows = _rows(result.output)
        assert [(r["type"], r["id"]) for r in rows] == [("X509", "x-1"), ("SSH", "s-1")]
        assert rows[1]["fingerprint"] == "SHA256:xyz"

    def test_list_empty_prints_header_only(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[]]
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "ca", "list"])
        assert result.output.strip() == "type,id,name,fingerprint"

    def test_list_auth_error_exits_nonzero(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.side_effect = TwingateAuthError("Bad token")
            assert runner.invoke(app, ["-s", SESSION, "ca", "list"]).exit_code != 0

    def test_show(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {"data": {"certificateAuthority": SSH}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "ca", "show", "-i", "s-1"])
        (row,) = _rows(result.output)
        assert row["type"] == "SSH" and row["name"] == "Vault SSH CA"

    def test_show_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "ca", "show"]).exit_code != 0


class TestCreate:
    def _invoke(self, args, key, payload, tmp_path, content="MATERIAL\n"):
        f = tmp_path / "ca.pem"
        f.write_text(content)
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.return_value = {"data": {key: payload}}
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "ca", "create", *args, "--file", str(f)])
        return result, inst

    def test_x509_sends_certificate(self, tmp_path):
        ok = {"ok": True, "error": None, "entity": {"id": "x-9", "name": "Corp", "fingerprint": "AA"}}
        result, inst = self._invoke(["-t", "x509", "-n", "Corp"], "x509CertificateAuthorityCreate", ok, tmp_path)
        assert result.exit_code == 0
        query, variables = inst.execute.call_args.args
        assert "x509CertificateAuthorityCreate" in query
        assert variables == {"name": "Corp", "certificate": "MATERIAL"}
        (row,) = _rows(result.output)
        assert row["ok"] == "True" and row["id"] == "x-9"

    def test_ssh_sends_public_key_and_type_is_case_insensitive(self, tmp_path):
        ok = {"ok": True, "error": None, "entity": {"id": "s-9", "name": "Vault", "fingerprint": "SHA256:q"}}
        _, inst = self._invoke(["-t", "SSH", "-n", "Vault"], "sshCertificateAuthorityCreate", ok, tmp_path)
        query, variables = inst.execute.call_args.args
        assert "sshCertificateAuthorityCreate" in query
        assert variables == {"name": "Vault", "publicKey": "MATERIAL"}

    def test_reports_api_error(self, tmp_path):
        bad = {"ok": False, "error": "Invalid certificate", "entity": None}
        result, _ = self._invoke(["-t", "x509", "-n", "x"], "x509CertificateAuthorityCreate", bad, tmp_path)
        assert "False" in result.output and "Invalid certificate" in result.output

    @pytest.mark.parametrize("args", [["-t", "pgp", "-n", "x"]])
    def test_invalid_type_rejected_before_any_api_call(self, args, tmp_path):
        result, inst = self._invoke(args, "x509CertificateAuthorityCreate", {}, tmp_path)
        assert result.exit_code != 0
        inst.execute.assert_not_called()

    def test_empty_and_missing_files_rejected_before_any_api_call(self, tmp_path):
        result, inst = self._invoke(["-t", "x509", "-n", "x"], "x509CertificateAuthorityCreate", {}, tmp_path, content="  \n")
        assert result.exit_code != 0
        inst.execute.assert_not_called()
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            missing = runner.invoke(
                app, ["-s", SESSION, "ca", "create", "-t", "x509", "-n", "x", "--file", str(tmp_path / "nope.pem")]
            )
            assert missing.exit_code != 0
            MockClient.return_value.execute.assert_not_called()

    @pytest.mark.parametrize("missing", ["-t", "-n", "--file"])
    def test_required_options(self, missing):
        args = {"-t": "x509", "-n": "x", "--file": "f"}
        argv = [x for k, v in args.items() if k != missing for x in (k, v)]
        assert runner.invoke(app, ["-s", SESSION, "ca", "create", *argv]).exit_code != 0


class TestDelete:
    def _invoke(self, found, mutation_key=None, payload=None):
        def execute(query, variables=None):
            if "certificateAuthority(id" in query:
                return {"data": {"certificateAuthority": found}}
            return {"data": {mutation_key: payload or {"ok": True, "error": None}}}

        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.side_effect = execute
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "ca", "delete", "-i", "ca-1"])
        return result, inst

    def test_x509_uses_x509_mutation(self):
        result, inst = self._invoke(X509, "x509CertificateAuthorityDelete")
        assert result.exit_code == 0 and result.output.split() == ["ok,error", "True,"]
        query, variables = inst.execute.call_args.args
        assert "x509CertificateAuthorityDelete" in query and variables == {"id": "ca-1"}

    def test_ssh_uses_ssh_mutation(self):
        result, inst = self._invoke(SSH, "sshCertificateAuthorityDelete")
        assert result.exit_code == 0
        assert "sshCertificateAuthorityDelete" in inst.execute.call_args.args[0]

    def test_unknown_id_errors_without_calling_a_delete_mutation(self):
        result, inst = self._invoke(None)
        assert result.exit_code != 0
        assert inst.execute.call_count == 1

    def test_reports_api_error(self):
        result, _ = self._invoke(X509, "x509CertificateAuthorityDelete", {"ok": False, "error": "CA is in use"})
        assert "False" in result.output and "in use" in result.output

    def test_requires_id(self):
        assert runner.invoke(app, ["-s", SESSION, "ca", "delete"]).exit_code != 0
