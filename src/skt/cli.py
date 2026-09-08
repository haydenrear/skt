"""skt command-line entry point.

Deliberately stdlib-only: the skill-script installer runs this file with
the system python3 (no venv), so nothing here may import beyond the
standard library until the install path grows a venv.
"""

from __future__ import annotations

import argparse
import sys

# A SECOND COPY, and it has to be one. `from . import __version__` would
# import the package __init__, which imports .artifacts -- breaking the
# stdlib-only contract in this module's docstring, under which the
# installer runs this file with the system python3 and no venv. So the
# literal stays, and `test_the_two_version_literals_agree` fails when it
# drifts from the package's: this bump missed it, and `skt --version`
# said 0.6.0 while the package said 0.7.0 with every test green.
__version__ = "0.8.1"

# Subcommand -> (implementing ticket, issue URL) for honest stubs.
# Empty since SKT-5; kept for future subcommands landing across tickets.
_PENDING: dict[str, tuple[str, str]] = {}

NOT_IMPLEMENTED_EXIT = 2


def _stub(name: str) -> int:
    ticket, issue = _PENDING[name]
    print(
        f"skt {name}: not implemented yet — lands with {ticket} ({issue})",
        file=sys.stderr,
    )
    return NOT_IMPLEMENTED_EXIT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skt",
        description=(
            "Skill-lifecycle CLI: startup disclosure of loaded skills/plugins, "
            "home tier and epic/ticket state; new-version, sync-with-root, unit-error "
            "and stale-artifact notifications; per-artifact rebuilds; worktree "
            "change management."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"skt {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser(
        "status",
        help="startup report: units, plugins, home tier, epic/ticket context (SKT-3)",
    )
    status.add_argument("--json", action="store_true", help="machine-readable output")

    check = sub.add_parser(
        "check",
        help="new-version, sync-with-root, unit-error and stale-artifact notifications",
    )
    check.add_argument("--cached", action="store_true", help="throttled, no-network path")
    check.add_argument("--ttl", type=int, default=900, help="cache freshness window in seconds")
    check.add_argument("--json", action="store_true")

    sync = sub.add_parser(
        "sync", help="pull a unit to its latest pushed source (SKT-4)"
    )
    sync.add_argument("unit", nargs="?")

    ticket = sub.add_parser(
        "ticket",
        help="worktree lifecycle: new/close/info via git-issue-workflow, plus "
        "list/sweep over every ticket worktree of the repository",
        # The SHAPE of a call, ahead of the option list. An eval watched an
        # agent guess the argument form and spend a call on the usage error;
        # argparse leads with options, and the verb-then-id order is the part
        # that is actually easy to get wrong.
        epilog=(
            "examples:\n"
            "  skt ticket new OUN-6                     from the derived path\n"
            "  skt ticket new OUN-6 --path ../wt-oun-6  epic mode, declared path\n"
            "  skt ticket new OUN-6 --base HEAD --path ../wt-oun-6\n"
            "  skt ticket close OUN-6                   resolves the path by search\n"
            "  skt ticket list --epic one-unit-one-name\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ticket.add_argument("verb", nargs="?", choices=["new", "close", "info", "list", "sweep"])
    ticket.add_argument("ticket_id", nargs="?")
    # THE POSITIONAL BASE, because the OTHER front door takes one.
    #
    # `wt new <ticket> <base>` is positional and is what git-issue-workflow
    # documents; `skt ticket new` took only `--base`. An agent that had read
    # the skill wrote `skt ticket new TICKET-42 main` and got
    #
    #     skt: error: unrecognized arguments: main
    #
    # -- measured in the ticket-open eval. Two doors onto one lifecycle that
    # disagree about how to spell the same argument is a trap for anyone who
    # learned either one, and the docs teach the spelling that failed.
    ticket.add_argument("base_pos", nargs="?", metavar="BASE",
                        help="base commit or ref, positional -- the same thing "
                             "--base names, accepted so `skt ticket new <ticket> "
                             "<base>` and `wt new <ticket> <base>` agree")
    ticket.add_argument("--base", help="base branch for ticket new")
    ticket.add_argument(
        "--path",
        help="epic mode: create the worktree at this DECLARED path (assignments "
        "name it) with the index-base pinning conventions, instead of wt's "
        "derived path",
    )
    ticket.add_argument(
        "--epic",
        help="list/sweep: limit to one epic's worktrees, by the slug in its "
        "epic/<slug> branch. Also selects the containment target. Discovered "
        "from the repository when there is exactly one epic branch.",
    )
    ticket.add_argument(
        "--target",
        help="list/sweep: the ref a ticket's commits must be contained in "
        "(default: the resolved epic branch)",
    )
    ticket.add_argument(
        "--into",
        help="sweep: the destination home for the `home close-out` gate "
        "(default: the MAIN working tree's .skill-manager)",
    )
    ticket.add_argument(
        "-y", "--yes", action="store_true",
        help="sweep: actually remove. Without it the sweep is a dry run that "
        "prints the plan and changes nothing.",
    )
    ticket.add_argument("--json", action="store_true", help="list/sweep: machine-readable output")

    build_cmd = sub.add_parser(
        "build",
        help="rebuild derived artifacts — one, some, or everything stale (ARTI-10)",
    )
    build_cmd.add_argument(
        "artifacts",
        nargs="*",
        help="artifact ids or short names, e.g. `computeq` or "
        "`cli-shim:skill-script/computeq`. With none, everything stale is built.",
    )
    build_cmd.add_argument("--stale", action="store_true", help="build every stale artifact")
    build_cmd.add_argument(
        "--all", action="store_true",
        help="build every artifact with a producer, stale or not",
    )
    build_cmd.add_argument("--dry-run", action="store_true", help="print what would be built")
    build_cmd.add_argument(
        "--force", action="store_true",
        help="rerun the install even when the recorded fingerprint still matches",
    )
    build_cmd.add_argument(
        "-y", "--yes", action="store_true", help="skip interactive confirmation"
    )
    build_cmd.add_argument("--json", action="store_true")

    publish = sub.add_parser(
        "publish", help="guided home-sync + unit-publish for edited skills"
    )
    publish.add_argument("unit", nargs="?")
    publish.add_argument("--check", action="store_true", help="list edited units only; exit 10 if any")
    publish.add_argument("--ticket", help="ticket id for the publish branch (default: inferred from branch)")

    return parser


def _import_sibling(name: str):
    """Import a package sibling whether run as a package or a bare script.

    The skill-script installer execs this file directly with the system
    python3, so relative imports need a bootstrapped sys.path.
    """
    if __package__:
        import importlib

        return importlib.import_module(f".{name}", package=__package__)
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import importlib

    return importlib.import_module(f"skt.{name}")



# The shape of each ticket verb, keyed by verb. `skt ticket new --help` is what
# an agent reaches for when it wants to know what `new` takes; argparse answers
# a flat `ticket` parser there, listing every flag of all five verbs with
# "list/sweep:" and "epic mode:" prefixes scattered through them. Measured in
# the epic-provisioning eval: the agent asked, got the wall, and guessed anyway.
#
# Intercepted rather than modelled as nested subparsers on purpose. Nesting
# would fix the help and break call shapes that work today -- `skt ticket
# --epic X list` puts the flag before the verb, and a subparser cannot see a
# flag that belongs to its parent.
TICKET_VERB_HELP = {
    "new": (
        "usage: skt ticket new <ticket> [<base>] [--base <ref>] [--path <dir>]\n"
        "\n"
        "Create the worktree AND its own Skill Manager home, in one command,\n"
        "rolled back together if the bootstrap fails.\n"
        "\n"
        "  <ticket>        the ticket id; the branch becomes feature/<ticket>\n"
        "  <base>          the base, positionally -- the same thing --base\n"
        "                  names. Accepted so this and `wt new <ticket>\n"
        "                  <base>` agree; --base wins if you give both.\n"
        "  --base <ref>    commit or ref to branch from. Resolve it FIRST and\n"
        "                  pass the SHA in epic mode -- a bare epic/<slug>\n"
        "                  names the local ref, which a server-side merge does\n"
        "                  not move. Must exist here; skt refuses rather than\n"
        "                  guessing.\n"
        "  --path <dir>    epic mode: put the worktree at this DECLARED path\n"
        "                  (assignments name it) instead of wt's derived one\n"
        "\n"
        "examples:\n"
        "  skt ticket new OUN-6\n"
        "  skt ticket new OUN-6 --base HEAD --path ../wt-oun-6\n"
    ),
    "close": (
        "usage: skt ticket close <ticket>\n"
        "\n"
        "Tear the worktree down through the close-out gate, which REFUSES\n"
        "while removing it would destroy unpublished skill work. Resolves the\n"
        "worktree by SEARCH, so a hand-made path is found too.\n"
        "\n"
        "  <ticket>        the ticket id\n"
        "\n"
        "exit 0 is the only code that means the worktree is gone.\n"
    ),
    "info": (
        "usage: skt ticket info <ticket>\n"
        "\n"
        "Print WORKTREE / BRANCH / BASE / LAUNCH / CLOSE for one ticket\n"
        "without changing anything.\n"
    ),
    "list": (
        "usage: skt ticket list [--epic <slug>] [--target <ref>] [--json]\n"
        "\n"
        "Every ticket worktree of this repository, with what each still holds.\n"
        "\n"
        "  --epic <slug>   limit to one epic's worktrees, by the slug in its\n"
        "                  epic/<slug> branch. Discovered from the repository\n"
        "                  when there is exactly one epic branch.\n"
        "  --target <ref>  the ref a ticket's commits must be contained in\n"
        "                  (default: the resolved epic branch)\n"
        "  --json          machine-readable output\n"
    ),
    "sweep": (
        "usage: skt ticket sweep [--epic <slug>] [--into <home>] [-y] [--json]\n"
        "\n"
        "Retire an epic's worktrees in one gated pass. WITHOUT -y this is a\n"
        "DRY RUN: it prints the plan and changes nothing.\n"
        "\n"
        "  --epic <slug>   limit to one epic's worktrees\n"
        "  --into <home>   destination home for the `home close-out` gate\n"
        "                  (default: the MAIN working tree's .skill-manager)\n"
        "  -y, --yes       actually remove\n"
        "  --json          machine-readable output\n"
    ),
}


def _ticket_verb_help(argv: list[str]) -> str | None:
    """The per-verb help text for `skt ticket <verb> --help`, or None.

    Only when a verb is present AND help is asked for. `skt ticket --help`
    still reaches argparse and prints the overview with all five verbs, which
    is the right answer to the question it asks.
    """
    if len(argv) < 2 or argv[0] != "ticket":
        return None
    if not any(a in ("-h", "--help") for a in argv[1:]):
        return None
    for arg in argv[1:]:
        if arg in TICKET_VERB_HELP:
            return TICKET_VERB_HELP[arg]
    return None


def main(argv: list[str] | None = None) -> int:
    verb_help = _ticket_verb_help(list(sys.argv[1:] if argv is None else argv))
    if verb_help is not None:
        sys.stdout.write(verb_help)
        return 0
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "status":
        return _import_sibling("status").run(as_json=args.json)
    if args.command == "check":
        return _import_sibling("check").run(as_json=args.json, cached=args.cached, ttl=args.ttl)
    if args.command == "sync":
        return _import_sibling("sync").run(args.unit)
    if args.command == "ticket":
        return _import_sibling("ticket").run(
            args.verb,
            args.ticket_id,
            # --base wins when both are given: an explicit flag beating a
            # positional is the least surprising rule, and it keeps every
            # existing call behaving exactly as it did.
            base=args.base or args.base_pos,
            path=args.path,
            epic=args.epic,
            target=args.target,
            into=args.into,
            yes=args.yes,
            as_json=args.json,
        )
    if args.command == "build":
        return _import_sibling("build_cmd").run(
            args.artifacts,
            stale_only=args.stale,
            all_artifacts=args.all,
            dry_run=args.dry_run,
            force=args.force,
            yes=args.yes,
            as_json=args.json,
        )
    if args.command == "publish":
        return _import_sibling("publish").run(args.unit, check_only=args.check, ticket=args.ticket)
    return _stub(args.command)


if __name__ == "__main__":
    sys.exit(main())
