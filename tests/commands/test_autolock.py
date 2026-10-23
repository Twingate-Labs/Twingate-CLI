"""Auto-lock is expressed as accessPolicy {mode: AUTO_LOCK, durationSeconds}; the deprecated usageBasedAutolockDurationDays is gone."""

from __future__ import annotations

import inspect
import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.commands.test_names_or_ids import G_ENG, G_OPS, RES, SA_CI
from tgcli.client.session import SessionManager
from tgcli.main import app
from tgcli.queries import resources as resource_queries

runner = CliRunner()
SESSION = "TestSess"
DAY = 86400


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


class Api:
    def __init__(self):
        self.requests: list[tuple[str, dict]] = []

    def execute(self, query, variables=None):
        self.requests.append((query, variables or {}))
        field = re.search(r"(resourceUpdate|resourceAccessAdd|resourceAccessSet)", query).group(1)
        entity = {"id": RES, "name": "R", "alias": None, "accessPolicy": {"mode": "AUTO_LOCK", "durationSeconds": 604800}, "approvalMode": "MANUAL"}
        return {"data": {field: {"ok": True, "error": None, "entity": entity}}}


def invoke(*args):
    api = Api()
    with patch("tgcli.commands._common.TwingateClient") as MockClient:
        MockClient.return_value.execute.side_effect = api.execute
        result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "resource", *args])
    return result, api


class TestAutolockCommand:
    def test_days_become_an_auto_lock_access_policy_in_seconds(self):
        result, api = invoke("autolock", "-i", RES, "-a", "7")
        assert result.exit_code == 0, result.output
        (query, variables), = api.requests
        assert variables == {"itemid": RES, "accessPolicy": {"mode": "AUTO_LOCK", "durationSeconds": 7 * DAY}, "autoapprovemode": "MANUAL"}
        assert "accessPolicy: $accessPolicy" in query and "usageBased" not in query

    @pytest.mark.parametrize("days", [1, 30, 365])
    def test_the_duration_is_days_times_86400(self, days):
        _, api = invoke("autolock", "-i", RES, "-a", str(days))
        assert api.requests[0][1]["accessPolicy"]["durationSeconds"] == days * DAY

    def test_minus_one_turns_auto_lock_off(self):
        result, api = invoke("autolock", "-i", RES, "-a", "-1")
        assert result.exit_code == 0 and api.requests[0][1]["accessPolicy"] == {"mode": "MANUAL"}

    def test_auto_approve_is_still_sent_alongside(self):
        _, api = invoke("autolock", "-i", RES, "-a", "7", "-r", "True")
        assert api.requests[0][1]["autoapprovemode"] == "AUTOMATIC"

    @pytest.mark.parametrize("days", ["0", "-2", "-30", "366", "1000"])
    def test_other_numbers_outside_1_to_365_are_refused_before_any_request(self, days):
        result, api = invoke("autolock", "-i", RES, "-a", days)
        assert result.exit_code == 1 and api.requests == [] and "from 1 to 365, or -1" in result.output

    def test_the_output_reports_the_new_access_policy(self):
        result, _ = invoke("autolock", "-i", RES, "-a", "7")
        header, row = result.stdout.splitlines()[:2]
        assert header == "ok,error,id,name,accessPolicy.mode,accessPolicy.durationSeconds,approvalMode"
        assert "AUTO_LOCK" in row and "604800" in row

    def test_autoapprove_also_reports_the_access_policy_and_not_the_deprecated_field(self):
        result, api = invoke("autoapprove", "-i", RES, "-r", "True")
        assert result.exit_code == 0 and "usageBased" not in api.requests[0][0]
        assert result.stdout.splitlines()[0].endswith("accessPolicy.mode,accessPolicy.durationSeconds,approvalMode")


class TestAccessAutolock:
    @pytest.mark.parametrize("sub", [["access", "add"], ["access", "set"], ["access_add"], ["access_set"]])
    def test_every_group_entry_gets_the_same_access_policy(self, sub):
        result, api = invoke(*sub, "-i", RES, "-g", f"{G_ENG},{G_OPS}", "-a", "7")
        assert result.exit_code == 0, result.output
        entries = api.requests[0][1]["accessids"]
        assert len(entries) == 2
        for entry in entries:
            assert entry["accessPolicy"] == {"mode": "AUTO_LOCK", "durationSeconds": 7 * DAY}
            assert "usageBasedAutolockDurationDays" not in entry

    @pytest.mark.parametrize("flags", [["-a", "7"], ["-e", "2027-01-01T00:00:00Z"], ["-a", "7", "-e", "2027-01-01T00:00:00Z"]])
    @pytest.mark.parametrize("sub", [["access", "add"], ["access", "set"], ["access_add"]])
    def test_autolock_and_expiry_are_refused_with_a_service_account_because_the_api_refuses_them(self, sub, flags):
        """Verified live: the API rejects both for a service account principal. Dropping them silently would grant wider access than asked for."""
        result, api = invoke(*sub, "-i", RES, "-g", G_ENG, "-s", SA_CI, *flags)
        assert result.exit_code == 1 and api.requests == []
        assert "can only be set on groups" in " ".join(result.output.split())

    def test_a_service_account_on_its_own_without_them_is_fine(self):
        result, api = invoke("access", "add", "-i", RES, "-s", SA_CI)
        assert result.exit_code == 0 and api.requests[0][1]["accessids"] == [{"principalId": SA_CI, "securityPolicyId": None}]

    def test_without_autolock_no_access_policy_is_sent(self):
        _, api = invoke("access", "add", "-i", RES, "-g", G_ENG)
        assert "accessPolicy" not in api.requests[0][1]["accessids"][0]

    @pytest.mark.parametrize("days", ["0", "-1", "-7", "366", "1000"])
    def test_days_outside_1_to_365_are_refused_before_any_request(self, days):
        result, api = invoke("access", "add", "-i", RES, "-g", G_ENG, "-a", days)
        assert result.exit_code == 1 and api.requests == [] and "from 1 to 365" in result.output

    def test_the_limits_themselves_are_accepted(self):
        for days in ("1", "365"):
            result, api = invoke("access", "add", "-i", RES, "-g", G_ENG, "-a", days)
            assert result.exit_code == 0 and api.requests[0][1]["accessids"][0]["accessPolicy"]["durationSeconds"] == int(days) * DAY


def test_no_query_or_mutation_uses_the_deprecated_field():
    """The API deprecated usageBasedAutolockDurationDays ("Use accessPolicy instead") and will eventually remove it, which would break every query naming it."""
    from tgcli.queries import backup, devices, groups, importing, networks  # noqa: F401
    import tgcli.queries as pkg
    import importlib
    import pkgutil

    offenders = []
    for module_info in pkgutil.iter_modules(pkg.__path__):
        module = importlib.import_module(f"tgcli.queries.{module_info.name}")
        for name, value in vars(module).items():
            if isinstance(value, str) and "usageBasedAutolockDurationDays" in value:
                offenders.append(f"{module_info.name}.{name}")
            elif isinstance(value, dict) and any("usageBasedAutolockDurationDays" in str(v) for v in value.values()):
                offenders.append(f"{module_info.name}.{name}")
    assert offenders == []
    assert "usageBasedAutolockDurationDays" not in inspect.getsource(resource_queries)
