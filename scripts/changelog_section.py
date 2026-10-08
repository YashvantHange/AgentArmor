"""Extract one version's section from CHANGELOG.md for a GitHub release body.

    python scripts/changelog_section.py v1.5.0 > release-notes.md

Replaces the hand-maintained docs/RELEASE_BODY.md, which shipped v1.4.0 notes as
the body of v1.4.1, v1.4.2 and v1.4.3 - including download instructions naming
installer files that did not exist in those releases. Nothing in the workflow
substituted a version into it and nothing failed when it went stale.

Exits non-zero when the section is missing, so a release fails loudly instead of
publishing someone else's notes. That makes a changelog entry a precondition for
cutting a release rather than a convention.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHANGELOG = REPO / "CHANGELOG.md"

INSTALL_BLOCK = """
---

## Windows (recommended)

1. Download **`AgentArmor_{version}_x64-setup.exe`** (or the `.msi`) from the assets below.
2. Run the installer.
3. Open **AgentArmor** and choose a scan type, or **Swarm** to run many agents at once.
4. Configure the target, run the scan, then review findings and export reports.

Multi-agent analysis runs on every scan and needs an analysis provider API key. Set
`AGENTARMOR_ANALYSIS_API_KEY`, or configure it in **Settings**.

## CLI

```bash
pip install agentarmor=={version}
```
"""


def normalize(tag: str) -> str:
    """Accept v1.5.0 or 1.5.0."""
    return tag[1:] if tag.startswith(("v", "V")) else tag


def extract(text: str, version: str) -> str | None:
    """Return the body of the `## [version]` section, heading excluded."""
    lines = text.splitlines()
    start: int | None = None
    pattern = re.compile(rf"^##\s*\[{re.escape(version)}\]")
    for index, line in enumerate(lines):
        if pattern.match(line):
            start = index + 1
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def main(argv: list[str]) -> int:
    # The changelog uses em dashes. Without this a non-UTF-8 console encoding
    # corrupts them on the way into the redirected release-notes file.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <tag>", file=sys.stderr)
        return 2

    version = normalize(argv[1])
    if not CHANGELOG.exists():
        print(f"error: {CHANGELOG} not found", file=sys.stderr)
        return 1

    body = extract(CHANGELOG.read_text(encoding="utf-8"), version)
    if not body:
        print(
            f"error: CHANGELOG.md has no '## [{version}]' section.\n"
            "Add the release section before tagging - the release body comes from it.",
            file=sys.stderr,
        )
        return 1

    print(f"## AgentArmor v{version}")
    print()
    print(body)
    print(INSTALL_BLOCK.format(version=version).rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
