"""Every version string in the repository agrees with agentarmor.__version__.

This exists because they did not. `pyproject.toml` carried its own static version
and the release checklist omitted `agentarmor/__init__.py`, so 1.4.1, 1.4.2 and
1.4.3 all shipped reporting **1.4.0** in `/health`, in the FastAPI title, in the
desktop status pill and stamped into every HTML and PDF report.

`pyproject.toml` can no longer drift - hatchling reads the version from
`__init__.py`. The GUI files still hold their own copies because Tauri and npm need
them literally, so a test is the only thing that keeps them honest. pytest is the
required check, so drift now fails CI rather than shipping.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# tomllib is 3.11+, and requires-python is >=3.10, so use the same conditional
# import core/config.py uses. CI runs 3.12, which would have hidden this.
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 only
    import tomli as tomllib  # type: ignore[no-redef]

import agentarmor

REPO = Path(__file__).resolve().parents[1]
VERSION = agentarmor.__version__


def test_the_version_is_a_release_number():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION


def test_pyproject_derives_its_version_from_the_package():
    """Not a matching literal - no literal at all, so the two cannot diverge."""
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in data["project"].get("dynamic", []), (
        "pyproject declares a static version again; that is what drifted before"
    )
    assert "version" not in data["project"]
    assert data["tool"]["hatch"]["version"]["path"] == "agentarmor/__init__.py"


def test_gui_package_json_matches():
    data = json.loads((REPO / "gui" / "package.json").read_text(encoding="utf-8"))
    assert data["version"] == VERSION


def test_tauri_config_matches():
    """The installer filenames are derived from this, so a mismatch misnames them."""
    data = json.loads(
        (REPO / "gui" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )
    assert data["version"] == VERSION


def test_tauri_cargo_manifest_matches():
    text = (REPO / "gui" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None, "no version in the Tauri Cargo.toml"
    assert match.group(1) == VERSION


def test_readme_badge_and_release_link_match():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert f"badge/version-{VERSION}-blue" in text
    # The version appears twice on the "Latest release" line: link text and tag URL.
    assert f"[v{VERSION}]" in text
    assert f"releases/tag/v{VERSION}" in text


def test_readme_names_the_current_installer():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert f"AgentArmor_{VERSION}_x64-setup.exe" in text


def test_the_github_action_installs_the_current_version():
    """Its default is what every documented use of the action gets.

    The README's own example does not pass `version`, so a stale default here is
    what users actually install.
    """
    text = (REPO / "action" / "action.yml").read_text(encoding="utf-8")
    assert f'default: "{VERSION}"' in text


def test_the_changelog_has_a_section_for_this_version():
    """The release workflow extracts its notes from here and fails without it."""
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{VERSION}]" in text


def test_the_stale_release_body_is_gone():
    """docs/RELEASE_BODY.md shipped v1.4.0 notes as the body of three releases.

    It named installer files that did not exist in those releases. Release notes are
    generated from the changelog now, so the file must not come back.
    """
    assert not (REPO / "docs" / "RELEASE_BODY.md").exists()
