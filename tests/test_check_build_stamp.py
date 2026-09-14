"""`skt check` names the builds that produced its verdict (skill-manager#338).

Asserted on ONE home judged through TWO skill-manager builds. A single-build
test cannot tell "the build is printed" from "a constant is printed"; this
one rewrites the home's pin between two passes and requires each verdict to
name its own build, the two verdicts to differ, and nothing but the build to
have moved.
"""

import json
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skt import check as check_mod  # noqa: E402
from skt import cli as cli_mod  # noqa: E402

from test_status import make_home, make_repo  # noqa: E402


def _pin(home: Path, release: str, build: str) -> None:
    """A real executable pin answering `--version` the way skill-manager does."""
    pin = home / "bin" / "cli" / "skill-manager"
    pin.parent.mkdir(parents=True, exist_ok=True)
    pin.write_text(
        "#!/bin/sh\n"
        f"echo 'skill-manager {release}'\n"
        f"echo 'build:  {build}'\n"
        "echo 'cli:    /somewhere/skill-manager'\n"
    )
    pin.chmod(pin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _without_build(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.startswith("  build: "))


def test_the_stamp_is_skill_managers_own_spelling():
    out = "skill-manager 0.27.2+gde4231386a9b\nbuild:  de4231386a9b (refs/heads/main)\ncli:    /x\n"
    assert check_mod._build_stamp(out) == (
        "skill-manager 0.27.2+gde4231386a9b @ de4231386a9b (refs/heads/main)"
    )
    # An older CLI with no build: line still names what it printed.
    assert check_mod._build_stamp("skill-manager 0.19.0\n") == "skill-manager 0.19.0"
    assert check_mod._build_stamp("") is None


def test_one_home_two_builds_two_verdicts(tmp_path, monkeypatch):
    # brew is not what this asserts about; keep it out of the pass.
    monkeypatch.setattr(check_mod, "_brew_latest", lambda timeout: (None, "no brew in test"))
    repo = make_repo(tmp_path / "repo")
    home = make_home(repo)

    _pin(home, "0.27.2+gaaaa1111bbbb", "aaaa1111bbbb (refs/heads/main)")
    first = check_mod.collect(repo, use_network=False, probe_artifacts=False,
                              probe_migration=False)
    _pin(home, "0.27.2", "artifact ffff66660000 built 2026-09-12T00:00:00Z (skill-manager.jar)")
    second = check_mod.collect(repo, use_network=False, probe_artifacts=False,
                               probe_migration=False)

    # --json: the fields name each pass's own build.
    assert first["skt_version"] == cli_mod.__version__ == second["skt_version"]
    assert "aaaa1111bbbb" in first["skill_manager_build"]
    assert "ffff66660000" not in first["skill_manager_build"]
    assert "ffff66660000" in second["skill_manager_build"]
    assert first["skill_manager_build"] != second["skill_manager_build"]
    assert first["cli"]["build"] == first["skill_manager_build"]
    json.dumps(first)  # still one serialisable document

    # text: a build line, different across the two builds, and the only change.
    text_a = check_mod.render_text(first)
    text_b = check_mod.render_text(second)
    assert f"  build: skt {cli_mod.__version__}; skill-manager 0.27.2+gaaaa1111bbbb @ aaaa1111bbbb" in text_a
    assert "ffff66660000" in text_b and "aaaa1111bbbb" not in text_b
    assert text_a != text_b
    assert _without_build(text_a) == _without_build(text_b)


def test_a_pass_that_consulted_no_build_says_so(tmp_path):
    repo = make_repo(tmp_path / "repo")
    make_home(repo)
    report = check_mod.collect(repo, use_network=False, probe_artifacts=False,
                               probe_cli=False, probe_migration=False)
    assert report["skill_manager_build"] is None
    text = check_mod.render_text(report)
    assert "  build: skt " in text
    assert "no skill-manager build consulted (off)" in text


def test_a_notification_verdict_carries_the_build_line_too():
    report = {
        "home": "/h", "tier": "root", "checked_units": ["a"], "skt_version": "9.9.9",
        "skill_manager_build": "skill-manager 0.27.2 @ abc (refs/heads/main)",
        "notifications": [{"kind": "new-version", "message": "a has a new version"}],
    }
    text = check_mod.render_text(report)
    assert text.splitlines()[-1] == "  build: skt 9.9.9; skill-manager 0.27.2 @ abc (refs/heads/main)"


def test_a_record_from_an_older_skt_does_not_invent_a_version():
    report = {"home": "/h", "tier": "root", "checked_units": [], "notifications": []}
    assert "version not recorded" in check_mod.render_text(report)
