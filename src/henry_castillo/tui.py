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

from henry_castillo import _log, render
from henry_castillo.content import Card, Demo

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
    try:
        webbrowser.open(url)
    except (webbrowser.Error, OSError) as exc:
        _log.logger.warning("browser launch failed: {}", exc)
        print(f"Couldn't open a browser; visit {url}")


def run(
    card: Card,
    *,
    console: Console,
    select: SelectFn | None = None,
    open_url: OpenUrlFn | None = None,
    update_available: bool = False,
    new_demos: Sequence[Demo] = (),
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
            if update_available and new_demos:
                console.print(
                    Text(
                        "New demos in a newer henry-castillo"
                        " — run `henry-castillo --update`:"
                    )
                )
                for demo in new_demos:
                    console.print(Text(f"● {demo.name} — {demo.summary}"))
            continue
        renderer = sections.get(choice)
        if renderer is None:
            continue
        console.print(renderer(card))
        if choice == _BLOG:
            url = render.blog_url(card.profile)
            if url is not None:
                open_url(url)
