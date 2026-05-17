"""CLI entrypoint.

Milestone 1.5 wires version reporting and auto-update. Real interactive
card + content subcommands arrive in Milestone 2; the default run is still
an intentional placeholder.
"""

from __future__ import annotations

import argparse
import os
import sys

from henry_castillo import __version__
from henry_castillo import update as _update

_BANNER = "henry-castillo {version}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="henry-castillo",
        description="Henry Castillo's personal CLI business card.",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="check whether a newer release exists and exit",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="upgrade henry-castillo to the latest release",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="skip the background update check on this run",
    )
    return parser


def _maybe_notice(args: argparse.Namespace) -> None:
    """Print a one-line update notice, only when interactive and allowed."""
    if args.no_update_check or os.environ.get("HENRY_CASTILLO_NO_UPDATE_CHECK"):
        return
    if not sys.stdout.isatty():  # never in pipes/CI/tests
        return
    latest = _update.check_for_update()
    if latest:
        print(_update.update_notice(latest))


def main(argv: list[str] | None = None) -> int:
    """Entry point for all six console aliases."""
    if argv is None:
        argv = sys.argv[1:]
    args = _build_parser().parse_args(argv)

    if args.version:
        print(_BANNER.format(version=__version__))
        return 0

    if args.update:
        return _update.perform_update()

    if args.check_update:
        latest = _update.check_for_update()
        if latest:
            print(
                f"henry-castillo {__version__}: a newer release {latest} "
                f"is available. Run `henry-castillo --update`."
            )
        else:
            print(f"henry-castillo {__version__} is up to date.")
        return 0

    print(_BANNER.format(version=__version__))
    print("Personal website + CLI business card — scaffold.")
    print("CLI features land in a later release.")
    print("Repo: https://github.com/d0rbu/d0rbu")
    _maybe_notice(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
