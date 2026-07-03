"""Interactive card loop: identity banner + arrow-key section menu.

Two-layer design for 100 % testability:
  Layer 1 -- ``run`` / ``_run_submenu``: pure logic driven by an injected
             ``prompt`` seam (fully tested without a terminal).
  Layer 2 -- ``_default_prompt``: real prompt_toolkit Application, tested
             by calling its pure handler helpers directly in unit tests.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from rich.console import Console
from rich.text import Text

from henry_castillo import _log, render
from henry_castillo.content import Card, Demo

OpenUrlFn = Callable[[str], None]


@dataclass(frozen=True)
class _Choice:
    id: str
    label: str
    disabled: str | None = None  # reason string if grayed/unselectable


# PromptFn: prompt(message, choices, default_index) -> (selected_or_None, moved)
PromptFn = Callable[[str, list["_Choice"], int], tuple["_Choice | None", bool]]


# ---------------------------------------------------------------------------
# Default open-url collaborator
# ---------------------------------------------------------------------------


def _default_open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except (webbrowser.Error, OSError) as exc:
        _log.logger.warning("browser launch failed: {}", exc)
        print(f"Couldn't open a browser; visit {url}")


# ---------------------------------------------------------------------------
# Layer 2 helpers — pure, callable without a terminal
# ---------------------------------------------------------------------------


def _render_menu(message: str, choices: list[_Choice], index: int) -> FormattedText:
    """Build the FormattedText list for the menu display.

    Separated so it can be called directly in tests (covering every row variant).
    """
    tokens: list[tuple[str, str]] = [("class:message", message + "\n")]
    for i, c in enumerate(choices):
        pointer = "❯ " if i == index else "  "
        if c.disabled is not None:
            tokens.append(("class:disabled", f"{pointer}{c.label} ({c.disabled})\n"))
        elif i == index:
            tokens.append(("class:selected", f"{pointer}{c.label}\n"))
        else:
            tokens.append(("", f"{pointer}{c.label}\n"))
    return FormattedText(tokens)


def _next_enabled(choices: list[_Choice], index: int, direction: int) -> int:
    """Return the next enabled index in *direction* (+1 down / -1 up).

    Clamps at the ends rather than wrapping. Returns *index* unchanged if
    no enabled item exists in that direction.
    """
    n = len(choices)
    candidate = index + direction
    while 0 <= candidate < n:
        if choices[candidate].disabled is None:
            return candidate
        candidate += direction
    return index  # clamped — no enabled item found


# ---------------------------------------------------------------------------
# Layer 2 — pure key-handler helpers (testable without a terminal)
# ---------------------------------------------------------------------------


@dataclass
class _PromptState:
    """Mutable state shared between key handlers and the prompt loop."""

    index: int
    moved: bool = False
    # result is initialized to (None, False) — the "quit without interaction" default.
    # key handlers overwrite it before calling app.exit().
    result: tuple[_Choice | None, bool] = field(default_factory=lambda: (None, False))


def _handle_up(state: _PromptState, choices: list[_Choice]) -> None:
    """Move the cursor up one enabled item."""
    new_idx = _next_enabled(choices, state.index, -1)
    if new_idx != state.index:
        state.moved = True
        state.index = new_idx


def _handle_down(state: _PromptState, choices: list[_Choice]) -> None:
    """Move the cursor down one enabled item."""
    new_idx = _next_enabled(choices, state.index, 1)
    if new_idx != state.index:
        state.moved = True
        state.index = new_idx


def _handle_enter(state: _PromptState, choices: list[_Choice]) -> bool:
    """Confirm selection; return True if the app should exit."""
    chosen = choices[state.index]
    if chosen.disabled is not None:
        return False  # ignore — disabled items should not be reachable
    state.result = (chosen, state.moved)
    return True


def _handle_quit(state: _PromptState) -> None:
    """Record a quit result."""
    state.result = (None, state.moved)


# ---------------------------------------------------------------------------
# Layer 2 -- _default_prompt (real prompt_toolkit Application)
# ---------------------------------------------------------------------------


def _make_prompt_app(
    message: str,
    choices: list[_Choice],
    state: _PromptState,
) -> Application:  # type: ignore[type-arg]
    """Build a prompt_toolkit Application for the given state.

    Extracted so tests can inspect the Application (e.g. call its text
    getter to cover the render path) without running the full event loop.
    """
    kb = KeyBindings()

    def _get_text() -> FormattedText:
        return _render_menu(message, choices, state.index)

    @kb.add("up")
    @kb.add("k")
    def _up(event: KeyPressEvent) -> None:
        _handle_up(state, choices)

    @kb.add("down")
    @kb.add("j")
    def _down(event: KeyPressEvent) -> None:
        _handle_down(state, choices)

    @kb.add("enter")
    def _enter(event: KeyPressEvent) -> None:
        if _handle_enter(state, choices):
            event.app.exit()

    @kb.add("q")
    @kb.add("c-c")
    @kb.add("c-d")
    def _quit(event: KeyPressEvent) -> None:
        _handle_quit(state)
        event.app.exit()

    return Application(
        layout=Layout(Window(content=FormattedTextControl(_get_text))),
        key_bindings=kb,
        full_screen=False,
    )


def _default_prompt(
    message: str, choices: list[_Choice], default_index: int
) -> tuple[_Choice | None, bool]:
    """Render an arrow-key selection menu; return (choice_or_None, moved).

    ``moved`` is True when the highlight changed at least once during this
    invocation (used by the arming logic in ``run``).
    """
    state = _PromptState(index=default_index)
    _make_prompt_app(message, choices, state).run()
    return state.result


# ---------------------------------------------------------------------------
# Layer 1 helpers — arming state machine for link items
# ---------------------------------------------------------------------------


def _handle_link(
    item_id: str,
    url: str | None,
    *,
    armed: str | None,
    moved: bool,
    console: Console,
    open_url: OpenUrlFn,
    not_configured_msg: str,
) -> str | None:
    """Handle a link item (blog / twitter / project).

    Returns the new value of ``armed``.
    """
    if url is None:
        console.print(Text(not_configured_msg))
        return None
    if item_id == armed and not moved:
        # Second (or later) press without moving — print the URL
        console.print(Text(url))
        return armed  # keep armed
    # First press or re-press after moving away — open browser + hint
    open_url(url)
    console.print(Text("Opened in browser. Didn't open? Press enter again for a URL."))
    return item_id


# ---------------------------------------------------------------------------
# Layer 1 -- submenu
# ---------------------------------------------------------------------------


def _run_submenu(
    card: Card,
    *,
    console: Console,
    prompt: PromptFn,
    open_url: OpenUrlFn,
) -> None:
    """Projects submenu — arrow-key list + Back."""
    proj_choices: list[_Choice] = [
        _Choice(f"project:{i}", p.name) for i, p in enumerate(card.projects)
    ]
    proj_choices.append(_Choice("back", "← Back"))

    armed: str | None = None
    default_index = 0

    while True:
        selected, moved = prompt(
            "Projects (↑/↓, Enter; q back)", proj_choices, default_index
        )
        if selected is None or selected.id == "back":
            return
        default_index = proj_choices.index(selected)

        # All project items are links
        raw_id = selected.id  # "project:<i>"
        i = int(raw_id.split(":", 1)[1])
        url: str | None = card.projects[i].url or None
        armed = _handle_link(
            raw_id,
            url,
            armed=armed,
            moved=moved,
            console=console,
            open_url=open_url,
            not_configured_msg=f"{card.projects[i].name} has no URL configured.",
        )


# ---------------------------------------------------------------------------
# Layer 1 -- main run loop
# ---------------------------------------------------------------------------


def run(
    card: Card,
    *,
    console: Console,
    prompt: PromptFn | None = None,
    open_url: OpenUrlFn | None = None,
    update_available: bool = False,
    new_demos: Sequence[Demo] = (),
) -> None:
    """Run the interactive TUI card loop."""
    prompt = prompt or _default_prompt
    open_url = open_url or _default_open_url

    # Build choices
    demos_choice: _Choice
    if update_available and new_demos:
        demos_choice = _Choice("demos", f"Demos — {len(new_demos)} new", None)
    else:
        demos_choice = _Choice("demos", "Demos", disabled="under construction")

    choices: list[_Choice] = [
        _Choice("about", "About"),
        _Choice("projects", "Projects"),
        _Choice("resume", "Résumé"),
        _Choice("contact", "Contact"),
        _Choice("blog", "Blog"),
        _Choice("twitter", "Twitter"),
        demos_choice,
        _Choice("quit", "Quit"),
    ]

    console.print(render.banner(card.profile))

    armed: str | None = None
    default_index = 0

    while True:
        selected, moved = prompt(
            "Navigate (↑/↓, Enter; q quits)", choices, default_index
        )
        if selected is None or selected.id == "quit":
            return
        default_index = choices.index(selected)

        sid = selected.id

        if sid == "about":
            console.print(render.about(card.profile))
            armed = None
        elif sid == "projects":
            _run_submenu(card, console=console, prompt=prompt, open_url=open_url)
            armed = None
        elif sid == "resume":
            console.print(render.resume(card))
            armed = None
        elif sid == "contact":
            console.print(render.contact(card.profile))
            armed = None
        elif sid == "blog":
            url = render.blog_url(card.profile)
            armed = _handle_link(
                "blog",
                url,
                armed=armed,
                moved=moved,
                console=console,
                open_url=open_url,
                not_configured_msg="Blog not configured yet.",
            )
        elif sid == "twitter":
            url = render.twitter_url(card.profile)
            armed = _handle_link(
                "twitter",
                url,
                armed=armed,
                moved=moved,
                console=console,
                open_url=open_url,
                not_configured_msg="Twitter not configured yet.",
            )
        else:
            # sid == "demos" — only reachable when demos_choice is enabled
            console.print(
                Text(
                    "New demos in a newer henry-castillo"
                    " — run `henry-castillo --update`:"
                )
            )
            for demo in new_demos:
                console.print(Text(f"● {demo.name} — {demo.summary}"))
            armed = None
