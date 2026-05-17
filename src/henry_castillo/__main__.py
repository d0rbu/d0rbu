"""Minimal CLI entrypoint stub.

Real functionality (interactive card + subcommands) arrives in Milestone 2.
This stub exists so the package and all six console aliases are verifiably
wired by Milestone 1.
"""

import sys

from henry_castillo import __version__


def main(argv: list[str] | None = None) -> int:
    """Print a friendly placeholder and exit 0."""
    if argv is None:
        argv = sys.argv[1:]
    print(f"henry-castillo {__version__}")
    print("Personal website + CLI business card — scaffold.")
    print("CLI features land in a later release.")
    print("Repo: https://github.com/d0rbu/d0rbu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
