"""CLI entrypoint: interactive card (TTY) or subcommands, content-driven.

Update-check behavior (`--version/--check-update/--update/--no-update-check`,
the throttled TTY-only offline-safe notice) is preserved from Milestone 1.5.
"""

from __future__ import annotations

import argparse
import os
import sys
import unicodedata
import webbrowser

from rich.console import Console
from rich.text import Text

from henry_castillo import __version__, content, render, tui
from henry_castillo import update as _update

_FALSEY_ENV = {"", "0", "false", "no", "off"}

_SEC_ABOUT = "about"
_SEC_PROJECTS = "projects"
_SEC_RESUME = "resume"
_SEC_RESUME_ACCENT = "résumé"
_SEC_CONTACT = "contact"
_SEC_SUBSTACK = "substack"


def _update_check_disabled_by_env() -> bool:
    val = os.environ.get("HENRY_CASTILLO_NO_UPDATE_CHECK")
    return val is not None and val.strip().lower() not in _FALSEY_ENV


def _harden_stream(stream: object) -> None:
    """Degrade un-encodable characters instead of crashing when the
    process stdout uses a restrictive codec (e.g.
    ``PYTHONIOENCODING=ascii`` in CI/Docker). The test harness swaps in a
    ``StringIO`` (no ``reconfigure``) — silently skipped there."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")


def _open_url(url: str) -> None:
    webbrowser.open(url)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="henry-castillo",
        description="Henry Castillo's personal CLI business card.",
        allow_abbrev=False,
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
    sub = parser.add_subparsers(dest="section")
    sub.add_parser(_SEC_ABOUT, help="show the about section")
    pp = sub.add_parser(_SEC_PROJECTS, help="list projects")
    pp.add_argument("--tag", help="filter projects by tag")
    rp = sub.add_parser(
        _SEC_RESUME, aliases=[_SEC_RESUME_ACCENT], help="show the résumé"
    )
    rp.add_argument(
        "--open",
        dest="open_resume",
        action="store_true",
        help="open the résumé PDF/web link in a browser",
    )
    sub.add_parser(_SEC_CONTACT, help="show contact info")
    sub.add_parser(_SEC_SUBSTACK, help="show the Substack link")
    return parser


def _maybe_notice(args: argparse.Namespace) -> None:
    if args.no_update_check or _update_check_disabled_by_env():
        return
    if not sys.stdout.isatty():
        return
    latest = _update.check_for_update()
    if latest:
        print(_update.update_notice(latest))


def _render_section(args: argparse.Namespace, console: Console) -> int:
    profile = content.load_profile()
    section = args.section
    if section == _SEC_ABOUT:
        console.print(render.about(profile))
    elif section == _SEC_PROJECTS:
        console.print(
            render.projects(content.load_projects(), tag=getattr(args, "tag", None))
        )
    elif section in (_SEC_RESUME, _SEC_RESUME_ACCENT):
        console.print(render.resume(profile))
        if getattr(args, "open_resume", False):
            pdf = profile.resume.pdf
            if pdf:
                _open_url(pdf)
            else:
                console.print(
                    Text(
                        "No résumé link set (`resume.pdf` in content/profile.json).",
                        style="dim",
                    )
                )
    elif section == _SEC_CONTACT:
        console.print(render.contact(profile))
    elif section == _SEC_SUBSTACK:
        console.print(render.substack(profile))
        url = render.substack_url(profile)
        if url is not None:
            _open_url(url)
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    _harden_stream(sys.stdout)
    argv = [unicodedata.normalize("NFC", a) for a in argv]
    args = _build_parser().parse_args(argv)

    if args.version:
        print(f"henry-castillo {__version__}")
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

    console = Console()
    if args.section is not None:
        rc = _render_section(args, console)
        _maybe_notice(args)
        return rc

    profile = content.load_profile()
    projects = content.load_projects()
    if sys.stdout.isatty():
        tui.run(profile, projects, console=console)
        _maybe_notice(args)
    else:
        render.render_all(console, profile, projects)
        _maybe_notice(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
