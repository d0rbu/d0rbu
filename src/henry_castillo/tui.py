"""Interactive card loop: identity banner + arrow-key section menu.

Side-effecting collaborators (`select`, `open_url`) are injected so the loop
is fully unit-testable without a real terminal. The defaults wrap
``questionary`` and ``webbrowser``.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable, Sequence

import questionary
from rich.console import Console
from rich.text import Text

from henry_castillo import render
from henry_castillo.content import Profile, Project

_MENU = [name for name, _ in render.SECTIONS]
_LAB_LOCKED = "Lab (locked)"
_QUIT = "Quit"
_SUBSTACK = "Substack"

SelectFn = Callable[[str, list[str]], str | None]
OpenUrlFn = Callable[[str], None]


def _default_select(message: str, choices: list[str]) -> str | None:
    try:
        return questionary.select(message, choices=choices).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def _default_open_url(url: str) -> None:
    webbrowser.open(url)


def run(
    profile: Profile,
    project_list: Sequence[Project],
    *,
    console: Console,
    select: SelectFn | None = None,
    open_url: OpenUrlFn | None = None,
) -> None:
    select = select or _default_select
    open_url = open_url or _default_open_url
    sections = dict(render.SECTIONS)
    choices = [*_MENU, _LAB_LOCKED, _QUIT]

    console.print(render.banner(profile))
    while True:
        choice = select("Navigate (↑/↓, Enter; q quits)", choices)
        if choice is None or choice == _QUIT:
            return
        if choice == _LAB_LOCKED:
            console.print(
                Text(
                    "Lab is locked — interactive ML experiments ship later as the "
                    "optional henry-castillo[lab] extra.",
                    style="dim",
                )
            )
            continue
        renderer = sections.get(choice)
        if renderer is None:
            continue
        console.print(renderer(profile, project_list))
        if choice == _SUBSTACK:
            url = render.substack_url(profile)
            if url is not None:
                open_url(url)
