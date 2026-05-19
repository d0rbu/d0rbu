"""Interactive card loop: identity banner + arrow-key section menu.

Side-effecting collaborators (`select`, `open_url`) are injected so the loop
is fully unit-testable without a real terminal. The defaults wrap
``questionary`` and ``webbrowser``.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable

import questionary
from rich.console import Console
from rich.text import Text

from henry_castillo import render
from henry_castillo.content import Card

_MENU = [name for name, _ in render.SECTIONS]
_DEMOS = "Demos (under construction)"
_QUIT = "Quit"
_BLOG = "Blog"

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
    card: Card,
    *,
    console: Console,
    select: SelectFn | None = None,
    open_url: OpenUrlFn | None = None,
    update_available: bool = False,
) -> None:
    select = select or _default_select
    open_url = open_url or _default_open_url
    sections = dict(render.SECTIONS)
    choices = [*_MENU, _DEMOS, _QUIT]

    console.print(render.banner(card.profile))
    while True:
        choice = select("Navigate (↑/↓, Enter; q quits)", choices)
        if choice is None or choice == _QUIT:
            return
        if choice == _DEMOS:
            console.print(Text("Demos are under construction…"))
            if update_available:
                console.print(
                    Text(
                        "● a newer henry-castillo is available — run"
                        " `henry-castillo --update`"
                    )
                )
            continue
        renderer = sections.get(choice)
        if renderer is None:
            continue
        console.print(renderer(card))
        if choice == _BLOG:
            url = render.blog_url(card.profile)
            if url is not None:
                open_url(url)
