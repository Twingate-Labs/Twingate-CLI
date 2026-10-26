"""Names outside the Windows code page, PowerShell-saved files, and report paths that cannot be written.

The legacy-encoding tests run the CLI in a subprocess with an ASCII locale and a cp1252 stdout: the closest a macOS or
Linux machine gets to a Windows console redirected to a file, where these commands used to crash with UnicodeEncodeError.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.commands.test_group_migrate import Api as MigrateApi
from tests.commands.test_group_migrate import group
from tests.importer.fake_api import FakeApi
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
NAME = "Ελληνικά 日本語 😀"
REPO = Path(__file__).resolve().parents[2]
LEGACY_ENV = {
    "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C", "LANG": "C",
}

PRELUDE = textwrap.dedent("""
    import keyring, sys
    from unittest.mock import patch
    store = {}
    keyring.set_password = lambda s, k, v: store.__setitem__((s, k), v)
    keyring.get_password = lambda s, k: store.get((s, k))
    import tgcli.main
    from tgcli.client.session import SessionManager
    SessionManager.store("S", "acme", "tok")
""")


def run_legacy(script: str, cwd: Path = REPO) -> subprocess.CompletedProcess:
    env = {**os.environ, **LEGACY_ENV}
    return subprocess.run([sys.executable, "-c", PRELUDE + textwrap.dedent(script)], cwd=cwd, env=env, capture_output=True)


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


class TestLegacyEncodings:
    def test_the_legacy_setup_really_is_narrow(self):
        done = run_legacy('print(sys.stdout.encoding); import locale; print(locale.getpreferredencoding(False))')
        stdout_encoding, default_encoding = done.stdout.decode().split()
        assert done.returncode == 0 and stdout_encoding == "cp1252" and default_encoding.lower().replace("-", "") in ("ascii", "usascii", "ansix3.41968")
        with pytest.raises(UnicodeEncodeError):
            NAME.encode(stdout_encoding)

    def test_csv_output_with_a_name_outside_the_code_page_is_written_as_utf_8(self):
        done = run_legacy(f"""
            node = {{"id": "d1", "name": {NAME!r}, "isTrusted": True, "osName": "Windows", "deviceType": "LAPTOP", "activeState": "ACTIVE",
                     "lastFailedLoginAt": None, "lastSuccessfulLoginAt": None, "osVersion": "11", "username": "u", "serialNumber": "SN1",
                     "user": {{"email": "a@b.com"}}, "clientVersion": "1", "internetSecurityConfiguration": "NONE"}}
            with patch("tgcli.commands._common.TwingateClient") as M:
                M.return_value.paginate.return_value = [[{{"node": node}}]]
                tgcli.main.app(["-s", "S", "-f", "csv", "device", "list"], standalone_mode=False)
        """)
        assert done.returncode == 0, done.stderr.decode()
        assert NAME in done.stdout.decode("utf-8")

    def test_group_migrate_writes_its_report_as_utf_8_and_does_not_crash(self, tmp_path):
        report = tmp_path / "report.csv"
        done = run_legacy(f"""
            from tests.commands.test_group_migrate import Api, group
            api = Api([group("s1", {NAME!r})])
            with patch("tgcli.commands._common.TwingateClient") as M:
                M.return_value.paginate.side_effect = api.paginate
                M.return_value.execute.side_effect = api.execute
                tgcli.main.app(["-s", "S", "group", "migrate", "--report", {str(report)!r}], standalone_mode=False)
        """)
        assert done.returncode == 0, done.stderr.decode()
        assert NAME in done.stdout.decode("utf-8")
        with open(report, newline="", encoding="utf-8") as handle:
            assert [r["source_group_name"] for r in csv.DictReader(handle)] == [NAME]

    def test_import_reads_a_utf_8_file_and_writes_its_report_as_utf_8(self, tmp_path):
        (tmp_path / "groups.csv").write_text(f"name\n{NAME}\n", encoding="utf-8")
        report = tmp_path / "report.csv"
        done = run_legacy(f"""
            from tests.importer.fake_api import FakeApi
            api = FakeApi()
            with patch("tgcli.commands._common.TwingateClient") as M:
                M.return_value.execute.side_effect = api.execute
                tgcli.main.app(["-s", "S", "import", {str(tmp_path)!r}, "--report", {str(report)!r}], standalone_mode=False)
        """)
        assert done.returncode == 0, done.stderr.decode()
        assert NAME in done.stdout.decode("utf-8")
        with open(report, newline="", encoding="utf-8") as handle:
            assert [r["name"] for r in csv.DictReader(handle)] == [NAME]


class TestFilesSavedByWindowsTools:
    DEVICE_IDS = ["RGV2aWNlOjE=", "RGV2aWNlOjI="]

    def known_ids(self, tmp_path, data):
        path = tmp_path / "ids.txt"
        path.write_bytes(data)
        return path

    def list_diff(self, path):
        node = lambda i: {"node": {"id": i, "name": i, "isTrusted": True, "osName": "x", "deviceType": "x", "activeState": "ACTIVE",
                                   "lastFailedLoginAt": None, "lastSuccessfulLoginAt": None, "osVersion": "1", "username": "u",
                                   "serialNumber": "S", "user": {"email": "a@b.c"}, "clientVersion": "1", "internetSecurityConfiguration": "NONE"}}
        with patch("tgcli.commands._common.TwingateClient") as M:
            M.return_value.paginate.return_value = [[node(i) for i in self.DEVICE_IDS]]
            return runner.invoke(app, ["-s", SESSION, "device", "list", "--fileofids", str(path)])

    @pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32"])
    def test_a_device_id_file_in_any_of_the_encodings_windows_writes(self, tmp_path, encoding):
        result = self.list_diff(self.known_ids(tmp_path, "\n".join(self.DEVICE_IDS).encode(encoding)))
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {"new": [], "missing": []}  # both IDs were read from the file, so nothing differs

    def test_a_device_id_file_that_is_not_text_is_a_clean_error(self, tmp_path):
        result = self.list_diff(self.known_ids(tmp_path, b"\xc3\x28 bad"))
        assert result.exit_code == 1 and "is not valid UTF-8 text" in result.output and isinstance(result.exception, SystemExit)

    def test_ca_certificate_files_with_a_byte_order_mark_or_utf_16(self, tmp_path):
        from tgcli.commands.certificate_authorities import _read_file
        pem = "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----"
        for name, data in {"a": pem.encode(), "b": b"\xef\xbb\xbf" + pem.encode(), "c": (pem + "\r\n").encode("utf-16")}.items():
            (tmp_path / name).write_bytes(data)
            assert _read_file(str(tmp_path / name)) == pem

    def test_a_ca_file_that_is_not_text_is_a_clean_error(self, tmp_path):
        from tgcli.commands.certificate_authorities import _read_file
        import typer
        (tmp_path / "x").write_bytes(b"\xc3\x28 bad")
        with pytest.raises(typer.Exit):
            _read_file(str(tmp_path / "x"))

    @pytest.mark.parametrize("data,label", [
        (b"\xef\xbb\xbf" + b'[{"name": "G\xc3\xa9"}]', "utf-8 with a byte order mark (Out-File -Encoding utf8)"),
        ('[{"name": "Gé"}]'.encode("utf-16"), "utf-16 (PowerShell 5.1 redirection)"),
    ])
    def test_import_json_saved_by_powershell(self, tmp_path, data, label):
        from tgcli.importer.load import load_file
        (tmp_path / "groups.json").write_bytes(data)
        assert [g.name for g in load_file(tmp_path / "groups.json", "groups")] == ["Gé"], label

    def test_import_csv_saved_by_powershell_as_utf_16(self, tmp_path):
        from tgcli.importer.load import load_file
        (tmp_path / "groups.csv").write_bytes("name,members\r\nGé,a@x.com\r\n".encode("utf-16"))
        (g,) = load_file(tmp_path / "groups.csv", "groups")
        assert (g.name, g.members) == ("Gé", ["a@x.com"])


class TestReportPathProblems:
    def bad_path(self, tmp_path):
        return str(tmp_path / "no-such-folder" / "report.csv")

    def test_group_migrate_refuses_before_reading_or_creating_anything(self, tmp_path):
        api = MigrateApi([group("s1", "Eng")])
        with patch("tgcli.commands._common.TwingateClient") as M:
            M.return_value.paginate.side_effect = api.paginate
            M.return_value.execute.side_effect = api.execute
            result = runner.invoke(app, ["-s", SESSION, "group", "migrate", "--execute", "--report", self.bad_path(tmp_path)])
        assert result.exit_code == 1 and "cannot write the report" in result.output and "Nothing was changed" in result.output
        assert api.writes == [] and api.calls == [] and isinstance(result.exception, SystemExit)

    def test_import_refuses_before_reading_the_tenant_or_changing_it(self, tmp_path):
        folder = tmp_path / "in"
        folder.mkdir()
        (folder / "groups.csv").write_text("name\nG\n", encoding="utf-8")
        api = FakeApi()
        with patch("tgcli.commands._common.TwingateClient") as M:
            M.return_value.execute.side_effect = api.execute
            result = runner.invoke(app, ["-s", SESSION, "import", str(folder), "--execute", "--report", self.bad_path(tmp_path)])
        assert result.exit_code == 1 and "cannot write the report" in result.output and "Nothing was changed" in result.output
        assert api.requests == []

    def test_import_whose_final_report_write_fails_still_says_what_happened(self, tmp_path):
        folder = tmp_path / "in"
        folder.mkdir()
        (folder / "groups.csv").write_text("name\nG\n", encoding="utf-8")
        api = FakeApi()
        with patch("tgcli.commands._common.TwingateClient") as M, patch("tgcli.commands.importing.write_report", side_effect=OSError(28, "No space left on device")):
            M.return_value.execute.side_effect = api.execute
            result = runner.invoke(app, ["-s", SESSION, "import", str(folder), "--execute", "--report", str(tmp_path / "r.csv")])
        assert result.exit_code == 1 and "report could not be written" in result.output and "No space left on device" in result.output
        assert "created" in result.output and len(api.writes) == 1  # the group was created and the summary says so

    def test_group_migrate_whose_final_report_write_fails_still_says_what_happened(self, tmp_path):
        api = MigrateApi([group("s1", "Eng")])
        real_open = open
        def failing_open(file, mode="r", *a, **kw):
            if str(file).endswith("r.csv") and "w" in mode:
                raise OSError(28, "No space left on device")
            return real_open(file, mode, *a, **kw)
        with patch("tgcli.commands._common.TwingateClient") as M, patch("tgcli.commands.groups.open", failing_open, create=True):
            M.return_value.paginate.side_effect = api.paginate
            M.return_value.execute.side_effect = api.execute
            result = runner.invoke(app, ["-s", SESSION, "group", "migrate", "--execute", "--report", str(tmp_path / "r.csv")])
        assert result.exit_code == 1 and "report could not be written" in result.output and "any group shown as created was created" in result.output
        assert len(api.created) == 1

    def test_a_good_path_still_works_and_leaves_exactly_one_report(self, tmp_path):
        api = MigrateApi([group("s1", "Eng")])
        report = tmp_path / "r.csv"
        with patch("tgcli.commands._common.TwingateClient") as M:
            M.return_value.paginate.side_effect = api.paginate
            M.return_value.execute.side_effect = api.execute
            result = runner.invoke(app, ["-s", SESSION, "group", "migrate", "--report", str(report)])
        assert result.exit_code == 0 and report.exists() and list(tmp_path.iterdir()) == [report]
