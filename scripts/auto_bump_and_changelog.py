from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "app" / "__init__.py"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"


@dataclass
class Version:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def tag(self) -> str:
        return f"v{self}"


def run(cmd: list[str]) -> str:
    out = subprocess.check_output(cmd, cwd=str(ROOT), text=True).strip()
    return out


def get_current_version() -> Version:
    text = VERSION_FILE.read_text(encoding="utf-8")
    m = re.search(r"__version__\s*=\s*[\"'](\d+)\.(\d+)\.(\d+)[\"']", text)
    if not m:
        raise RuntimeError("__version__ not found in app/__init__.py")
    return Version(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def set_version(new_version: Version) -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    text = re.sub(
        r"(__version__\s*=\s*[\"'])(\d+\.\d+\.\d+)([\"'])",
        rf"\g<1>{new_version}\g<3>",
        text,
    )
    VERSION_FILE.write_text(text, encoding="utf-8")


def last_tag_or_none() -> str | None:
    try:
        return run(["git", "describe", "--tags", "--abbrev=0"]) or None
    except subprocess.CalledProcessError:
        return None


def commits_since(ref: str | None) -> list[str]:
    if ref:
        rng = f"{ref}..HEAD"
    else:
        rng = "HEAD"
    try:
        raw = run(["git", "log", "--pretty=%s", rng])
    except subprocess.CalledProcessError:
        return []
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    # Filter out our own bot bumps to avoid noisy changelog entries
    return [l for l in lines if not l.lower().startswith("chore: bump version")]  # simplistic filter


def infer_bump_level(messages: list[str]) -> str:
    level = os.getenv("BUMP_LEVEL", "auto").lower()
    if level in {"major", "minor", "patch"}:
        return level
    text = "\n".join(messages).lower()
    if "breaking change" in text or re.search(r"\bfeat!\b|\bfix!\b|!:", text):
        return "major"
    if re.search(r"\bfeat\b|\bfeature\b", text):
        return "minor"
    return "patch"


def bumped(v: Version, level: str) -> Version:
    if level == "major":
        return Version(v.major + 1, 0, 0)
    if level == "minor":
        return Version(v.major, v.minor + 1, 0)
    return Version(v.major, v.minor, v.patch + 1)


def update_changelog(new_version: Version, messages: list[str]) -> None:
    today = date.today().isoformat()
    header = f"## v{new_version} - {today}\n\n"
    if messages:
        body = "\n".join(f"- {m}" for m in messages)
    else:
        body = "- Internal changes"
    section = header + body + "\n\n"
    if CHANGELOG_FILE.exists():
        existing = CHANGELOG_FILE.read_text(encoding="utf-8")
    else:
        existing = "# Changelog\n\n"
    CHANGELOG_FILE.write_text(existing + section, encoding="utf-8")


def commit_and_tag(new_version: Version) -> None:
    run(["git", "config", "user.name", os.getenv("GIT_USER_NAME", "github-actions[bot]")])
    run(["git", "config", "user.email", os.getenv("GIT_USER_EMAIL", "github-actions[bot]@users.noreply.github.com")])
    run(["git", "add", str(VERSION_FILE), str(CHANGELOG_FILE)])
    run(["git", "commit", "-m", f"chore: bump version to v{new_version}"])
    run(["git", "tag", f"v{new_version}"])


def main() -> None:
    base = get_current_version()
    ref = last_tag_or_none()
    messages = commits_since(ref)
    level = infer_bump_level(messages)
    new_v = bumped(base, level)
    set_version(new_v)
    update_changelog(new_v, messages)
    commit_and_tag(new_v)
    # Push only when running in CI; locally you can run manually
    if os.getenv("CI"):
        run(["git", "push", "--follow-tags"])


if __name__ == "__main__":
    main()
