"""Delete commands ask before deleting, and a script has to say --yes.

Asked on an interactive terminal; with no terminal (a script, cron, a pipe) the command refuses instead of guessing.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.session import SessionManager
from tgcli.main import app  # must come before tgcli.commands._common (circular import otherwise)

runner = CliRunner()
SESSION = "TestSess"

DELETES = [
    ["account", "delete", "-i", "x1"],
    ["connector", "delete", "-i", "x1"],
    ["group", "delete", "-i", "x1"],
    ["gateway", "delete", "-i", "x1"],
    ["network", "delete", "-i", "x1"],
    ["user", "delete", "-i", "x1"],
    ["resource", "delete", "-i", "x1"],
    ["key", "delete", "-i", "x1"],
    ["key", "revoke", "-i", "x1"],
    ["ca", "delete", "-i", "x1"],
    ["dns-profile", "delete", "-i", "x1"],
]
IDS = [" ".join(a[:2]) for a in DELETES]


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


class Api:
    """Answers reads with something that exists and every mutation with ok, and records the mutations."""

    def __init__(self, exists=True):
        self.exists, self.writes, self.reads = exists, [], 0

    def execute(self, query, variables=None):
        if query.lstrip().startswith("query"):
            self.reads += 1
            found = {"__typename": "X509CertificateAuthority", "id": "x1"} if self.exists else None
            return {"data": {"certificateAuthority": found, "dnsFilteringProfile": found}}
        self.writes.append(variables)
        return {"data": {name: {"ok": True, "error": None, "entity": {"id": "x1"}} for name in (
            "serviceAccountDelete", "connectorDelete", "groupDelete", "gatewayDelete", "remoteNetworkDelete", "userDelete",
            "resourceDelete", "serviceAccountKeyDelete", "serviceAccountKeyRevoke", "certificateAuthorityDelete", "x509CertificateAuthorityDelete",
            "sshCertificateAuthorityDelete", "dnsFilteringProfileDelete", "remoteNetworkUpdate")}}


def run(api, argv, terminal, answer=None, *extra):
    with patch("tgcli.commands._common.TwingateClient") as MockClient, patch("tgcli.commands._common._at_a_terminal", return_value=terminal):
        MockClient.return_value.execute.side_effect = api.execute
        return runner.invoke(app, ["-s", SESSION, "-f", "csv", *argv, *extra], input=answer)


@pytest.mark.parametrize("argv", DELETES, ids=IDS)
class TestEveryDeleteCommand:
    def test_with_no_terminal_and_no_yes_it_refuses_and_changes_nothing(self, argv):
        api = Api()
        result = run(api, argv, terminal=False)
        assert result.exit_code == 1 and api.writes == []
        assert "without confirmation" in result.stderr and "--yes" in result.stderr and "x1" in result.stderr
        assert result.stdout == ""

    def test_with_no_terminal_yes_deletes(self, argv):
        api = Api()
        result = run(api, argv, False, None, "--yes")
        assert result.exit_code == 0, result.output
        assert len(api.writes) == 1

    def test_the_short_flag_is_the_same(self, argv):
        api = Api()
        assert run(api, argv, False, None, "-y").exit_code == 0 and len(api.writes) == 1

    def test_on_a_terminal_it_asks_and_yes_deletes(self, argv):
        api = Api()
        result = run(api, argv, True, "y\n")
        assert result.exit_code == 0, result.output
        assert len(api.writes) == 1 and "x1" in result.stderr and "[y/N]" in result.stderr

    @pytest.mark.parametrize("answer", ["n\n", "\n", "no\n", "maybe\nn\n"])
    def test_on_a_terminal_anything_but_yes_deletes_nothing(self, argv, answer):
        api = Api()
        result = run(api, argv, True, answer)
        assert result.exit_code == 1 and api.writes == []
        assert "Nothing was" in result.stderr

    def test_on_a_terminal_closed_input_deletes_nothing(self, argv):
        api = Api()
        result = run(api, argv, True, "")
        assert result.exit_code != 0 and api.writes == []

    def test_on_a_terminal_yes_flag_does_not_ask(self, argv):
        api = Api()
        result = run(api, argv, True, None, "--yes")
        assert result.exit_code == 0 and "[y/N]" not in result.output and len(api.writes) == 1

    def test_the_question_does_not_pollute_standard_output(self, argv):
        result = run(Api(), argv, True, "y\n")
        assert "[y/N]" not in result.stdout and "Delete" not in result.stdout and "Revoke" not in result.stdout

    def test_help_lists_the_option(self, argv):
        result = runner.invoke(app, [*argv[:2], "--help"])
        assert "--yes" in result.output and "-y" in result.output


class TestWording:
    def test_a_revoke_says_revoke(self):
        result = run(Api(), ["key", "revoke", "-i", "x1"], True, "n\n")
        assert "Revoke Service Account Key x1?" in result.stderr and "Nothing was revoked." in result.stderr
        refused = run(Api(), ["key", "revoke", "-i", "x1"], False)
        assert "refusing to revoke" in refused.stderr and "Pass --yes to revoke it" in refused.stderr

    def test_a_delete_says_delete(self):
        result = run(Api(), ["group", "delete", "-i", "x1"], True, "n\n")
        assert "Delete Group x1?" in result.stderr and "Nothing was deleted." in result.stderr


class TestOrder:
    @pytest.mark.parametrize("argv", [["ca", "delete", "-i", "x1"], ["dns-profile", "delete", "-i", "x1"]], ids=["ca", "dns-profile"])
    def test_a_missing_object_is_reported_before_any_question(self, argv):
        api = Api(exists=False)
        result = run(api, argv, True, None)
        assert result.exit_code == 1 and "not found" in result.stderr and "[y/N]" not in result.output and api.writes == []

    def test_a_missing_session_is_reported_before_any_question(self):
        with patch("tgcli.commands._common._at_a_terminal", return_value=True):
            result = runner.invoke(app, ["group", "delete", "-i", "x1"])
        assert result.exit_code == 1 and "No session name" in result.stderr and "[y/N]" not in result.output

    def test_other_commands_never_ask(self):
        api = Api()
        result = run(api, ["network", "updateName", "-i", "x1", "-n", "new"], False)
        assert result.exit_code == 0, result.output
        assert len(api.writes) == 1 and "without confirmation" not in result.output and "[y/N]" not in result.output
