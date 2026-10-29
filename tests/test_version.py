"""The version lives in three places; a release must change them together."""

from __future__ import annotations

import re
from pathlib import Path

from tgcli import VERSION
from tgcli.client.client import USER_AGENT

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_and_the_package_report_the_same_version():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1) == VERSION


def test_the_user_agent_carries_the_package_version():
    assert USER_AGENT == f"TwingatePythonCLI/{VERSION}"


def test_the_readme_shows_the_current_version():
    assert f"# tgcli version {VERSION}" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_changelog_has_an_entry_for_the_current_version():
    assert re.search(rf"^## \[{re.escape(VERSION)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
