import subprocess
import sys
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parents[1] / "src" / "skt" / "cli.py"

PENDING_COMMANDS = []  # all subcommands implemented as of SKT-5


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args], capture_output=True, text=True
    )


def test_entry_point_importable():
    sys.path.insert(0, str(CLI.parents[1]))
    from skt.cli import main  # noqa: F401


def test_help_runs_clean():
    result = run("--help")
    assert result.returncode == 0
    assert "skt" in result.stdout


def test_version():
    result = run("--version")
    assert result.returncode == 0
    from skt import __version__ as pkg_version
    assert result.stdout.strip() == f"skt {pkg_version}"


def test_the_two_version_literals_agree():
    """`skt.cli` must keep its own copy, so something has to check it.

    cli.py is stdlib-only by contract -- the skill-script installer runs
    it with the system python3 and no venv -- so it cannot import the
    package to learn the version, and the duplicate literal is deliberate.
    What is NOT acceptable is the duplicate drifting silently: the 0.7.0
    bump moved three manifests and `skt/__init__.py`, left this one at
    0.6.0, and every test still passed because the only assertion read
    the stale copy.
    """
    from skt import __version__ as pkg_version
    from skt.cli import __version__ as cli_version
    assert cli_version == pkg_version, (
        f"skt.cli.__version__ is {cli_version} but the package says "
        f"{pkg_version} — bump both, they cannot import each other"
    )


def test_no_args_prints_help():
    result = run()
    assert result.returncode == 0
    assert "startup report" in result.stdout


@pytest.mark.parametrize("command", PENDING_COMMANDS)
def test_pending_commands_are_honest_stubs(command):
    result = run(command)
    assert result.returncode == 2
    assert "not implemented yet" in result.stderr
    assert "SKT-" in result.stderr


@pytest.mark.parametrize("command", PENDING_COMMANDS)
def test_pending_commands_have_help(command):
    result = run(command, "--help")
    assert result.returncode == 0


# --- `skt ticket <verb> --help` answers about the VERB ----------------------
#
# The eval that produced this asked `skt ticket new --help` and got the flat
# `ticket` parser: every flag of all five verbs, prefixed "list/sweep:" and
# "epic mode:", with nothing saying which ones `new` takes. Exit 0 and useless
# is a worse failure than exit 1, because nothing marks it as a non-answer.

TICKET_VERBS = ["new", "close", "info", "list", "sweep"]


@pytest.mark.parametrize("verb", TICKET_VERBS)
def test_ticket_verb_help_is_about_that_verb(verb):
    result = run("ticket", verb, "--help")
    assert result.returncode == 0
    assert result.stdout.startswith(f"usage: skt ticket {verb}"), result.stdout


# A flag belongs to some verbs and not others. The flat parser listed all of
# them at once and disambiguated in prose ("list/sweep: ..."), which is the
# thing that made it unreadable. Per-verb help has nothing to disambiguate
# FROM, so a flag that is not this verb's must be absent -- not merely
# labelled. ("epic mode:" stays in `new`'s help: --path really is a mode of
# new, not a cross-reference to another verb. The first version of this test
# asserted otherwise and was wrong about the code, not the code about itself.)
FLAGS_NOT_FOR = {
    "new": ["--epic", "--target", "--into", "--json", "--yes"],
    "close": ["--base", "--path", "--epic", "--into", "--json"],
    "info": ["--base", "--path", "--into", "--yes"],
    "list": ["--base", "--path", "--into", "--yes"],
    "sweep": ["--base", "--path", "--target"],
}


@pytest.mark.parametrize("verb", TICKET_VERBS)
def test_ticket_verb_help_omits_other_verbs_flags(verb):
    """Non-vacuity: the whole point is that it is SHORTER and NARROWER."""
    result = run("ticket", verb, "--help")
    overview = run("ticket", "--help")
    assert len(result.stdout) < len(overview.stdout)
    assert "list/sweep:" not in result.stdout
    for flag in FLAGS_NOT_FOR[verb]:
        assert flag not in result.stdout, f"{verb} help mentions {flag}"


def test_ticket_help_without_a_verb_still_lists_them_all():
    """The overview answers a different question and is left alone."""
    result = run("ticket", "--help")
    assert result.returncode == 0
    for verb in TICKET_VERBS:
        assert verb in result.stdout


def test_ticket_verb_help_does_not_swallow_a_real_call():
    """`--help` must be the only thing this intercepts.

    A guard that fired on any argv containing a verb would turn every
    `skt ticket new <id>` into a help screen and create no worktree.
    """
    result = run("ticket", "new")
    assert not result.stdout.startswith("usage: skt ticket new <ticket>")
