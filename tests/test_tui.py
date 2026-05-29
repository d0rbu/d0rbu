"""Tests for tui.py — 100 % line + branch coverage, zero pragma.

Two-layer strategy:
  Layer 1 tests: inject a fake ``prompt`` returning scripted (_Choice, moved)
                 tuples — exercise all logic branches in ``run``/``_run_submenu``.
  Layer 2 tests: drive ``_default_prompt`` via prompt_toolkit pipe-input +
                 DummyOutput — exercise every key-handler / render branch.
"""

from __future__ import annotations

import _socket
import contextlib
import io
import socket as _socket_mod
import webbrowser
from collections.abc import Callable

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from henry_castillo import tui
from henry_castillo.content import (
    Card,
    Demo,
    parse_card,
)
from henry_castillo.tui import _Choice, _next_enabled, _render_menu

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_TUI_PROFILE_DOC: dict[str, object] = {
    "name": "Henry Castillo",
    "handle": "d0rbu",
    "tagline": "ML",
    "about": "Bio.",
    "email": "e@x.y",
    "links": {
        "github": "https://github.com/d0rbu",
        "blog": "https://s.substack.com",
        "twitter": "https://twitter.com/d0rbu",
    },
}
_VALID_DOC: dict[str, object] = {
    "schema_version": 2,
    "profile": _TUI_PROFILE_DOC,
    "projects": [
        {
            "name": "p1",
            "blurb": "b1",
            "url": "https://example.com/p1",
            "tags": ["t"],
        },
        {
            "name": "p2",
            "blurb": "b2",
            "url": "https://example.com/p2",
            "tags": [],
        },
    ],
    "resume": {
        "pdf": "",
        "experience": [],
        "education": [],
        "highlights": [],
    },
    "demos": [],
}

CARD: Card = parse_card(_VALID_DOC)


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=80, no_color=True), buf


# ---------------------------------------------------------------------------
# Fake prompt helpers
# ---------------------------------------------------------------------------


def _choice(cid: str, choices: list[_Choice]) -> _Choice:
    """Look up a choice by id."""
    for c in choices:
        if c.id == cid:
            return c
    raise KeyError(cid)


def _scripted_prompt(
    *steps: tuple[str | None, bool],
) -> tui.PromptFn:
    """Return a prompt function that pops (choice_id, moved) from *steps*.

    Passing id=None means return (None, moved) — simulates quit/ctrl-c.
    The last step may be reused if the iterator is exhausted.
    """
    it = iter(steps)
    last: tuple[str | None, bool] = (None, False)

    def _prompt(
        _message: str, choices: list[_Choice], _default_index: int
    ) -> tuple[_Choice | None, bool]:
        nonlocal last
        with contextlib.suppress(StopIteration):
            last = next(it)  # type: ignore[assignment]
        cid, moved = last
        if cid is None:
            return (None, moved)
        return (_choice(cid, choices), moved)

    return _prompt


def _recording_prompt(
    *steps: tuple[str | None, bool],
) -> tuple[tui.PromptFn, list[tuple[str, list[_Choice], int]]]:
    """Like _scripted_prompt but also records every call for assertions."""
    calls: list[tuple[str, list[_Choice], int]] = []
    it = iter(steps)
    last: tuple[str | None, bool] = (None, False)

    def _prompt(
        message: str, choices: list[_Choice], default_index: int
    ) -> tuple[_Choice | None, bool]:
        nonlocal last
        with contextlib.suppress(StopIteration):
            last = next(it)  # type: ignore[assignment]
        calls.append((message, list(choices), default_index))
        cid, moved = last
        if cid is None:
            return (None, moved)
        return (_choice(cid, choices), moved)

    return _prompt, calls


# ===========================================================================
# Layer 1 — run() logic
# ===========================================================================


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


def test_banner_printed_once():
    console, buf = _console()
    prompt, _ = _recording_prompt(
        ("about", False),
        ("projects", False),
        (None, False),
    )
    tui.run(CARD, console=console, prompt=prompt, open_url=lambda _u: None)
    assert buf.getvalue().count("Henry Castillo") == 1


# ---------------------------------------------------------------------------
# Quit paths
# ---------------------------------------------------------------------------


def test_none_result_quits():
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt((None, False)),
        open_url=lambda _u: None,
    )
    assert "Henry Castillo" in buf.getvalue()
    assert "Bio." not in buf.getvalue()


def test_quit_choice_exits_loop():
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("quit", False)),
        open_url=lambda _u: None,
    )
    assert "Henry Castillo" in buf.getvalue()
    assert "Bio." not in buf.getvalue()


# ---------------------------------------------------------------------------
# Section renders
# ---------------------------------------------------------------------------


def test_about_renders():
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("about", False), (None, False)),
        open_url=lambda _u: None,
    )
    assert "Bio." in buf.getvalue()


def test_resume_renders():
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("resume", False), (None, False)),
        open_url=lambda _u: None,
    )
    assert "Résumé" in buf.getvalue()


def test_contact_renders():
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("contact", False), (None, False)),
        open_url=lambda _u: None,
    )
    assert "e@x.y" in buf.getvalue()


# ---------------------------------------------------------------------------
# Blog link item — arming state machine
# ---------------------------------------------------------------------------


def test_blog_first_press_opens_url_and_shows_hint():
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("blog", False), (None, False)),
        open_url=opened.append,
    )
    assert opened == ["https://s.substack.com"]
    assert "Opened in browser" in buf.getvalue()


def test_blog_stay_press_prints_url():
    """Second press without moving (moved=False, same id armed) prints URL."""
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        # first press: open + arm; second: armed="blog", not moved -> print URL
        prompt=_scripted_prompt(("blog", False), ("blog", False), (None, False)),
        open_url=opened.append,
    )
    assert opened == ["https://s.substack.com"]  # only one open call
    out = buf.getvalue()
    stripped_lines = [line.strip() for line in out.splitlines()]
    assert any(ln == "https://s.substack.com" for ln in stripped_lines)


def test_blog_move_away_and_back_reopens():
    """Navigate to another item then back -> moved=True -> re-open."""
    opened: list[str] = []
    console, _buf = _console()
    tui.run(
        CARD,
        console=console,
        # open + arm, then away (resets armed), then back moved=True -> re-open
        prompt=_scripted_prompt(
            ("blog", False),  # open + arm
            ("about", True),  # renders about, armed=None
            ("blog", True),  # moved=True -> re-open
            (None, False),
        ),
        open_url=opened.append,
    )
    assert len(opened) == 2  # opened twice


def test_blog_unconfigured_prints_message_no_open():
    doc = {
        **_VALID_DOC,
        "profile": {
            **_TUI_PROFILE_DOC,
            "links": {"github": "https://github.com/d0rbu", "blog": "", "twitter": ""},
        },
    }
    card = parse_card(doc)
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        card,
        console=console,
        prompt=_scripted_prompt(("blog", False), (None, False)),
        open_url=opened.append,
    )
    assert opened == []
    assert "Blog not configured yet." in buf.getvalue()


# ---------------------------------------------------------------------------
# Twitter link item — arming state machine
# ---------------------------------------------------------------------------


def test_twitter_first_press_opens_url():
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("twitter", False), (None, False)),
        open_url=opened.append,
    )
    assert opened == ["https://twitter.com/d0rbu"]
    assert "Opened in browser" in buf.getvalue()


def test_twitter_stay_press_prints_url():
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(
            ("twitter", False),  # open + arm
            ("twitter", False),  # stay -> print URL
            (None, False),
        ),
        open_url=opened.append,
    )
    assert opened == ["https://twitter.com/d0rbu"]
    out = buf.getvalue()
    stripped_lines = [line.strip() for line in out.splitlines()]
    assert any(ln == "https://twitter.com/d0rbu" for ln in stripped_lines)


def test_twitter_unconfigured_prints_message():
    doc = {
        **_VALID_DOC,
        "profile": {
            **_TUI_PROFILE_DOC,
            "links": {
                "github": "https://github.com/d0rbu",
                "blog": "https://s.substack.com",
                "twitter": "",
            },
        },
    }
    card = parse_card(doc)
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        card,
        console=console,
        prompt=_scripted_prompt(("twitter", False), (None, False)),
        open_url=opened.append,
    )
    assert opened == []
    assert "Twitter not configured yet." in buf.getvalue()


# ---------------------------------------------------------------------------
# Demos item
# ---------------------------------------------------------------------------


_ALPHA = Demo("alpha", "does alpha", "0.2.0")
_BETA = Demo("beta", "does beta", "0.3.0")


def _demos_run(*, update_available: bool, new_demos: list[Demo]) -> str:
    console, buf = _console()
    # When demos is disabled, its id="demos" is still in choices but disabled.
    # We pick a non-disabled item to select (quit), since disabled items
    # should never be selected in practice.  For the enabled case we DO select demos.
    if update_available and new_demos:
        prompt = _scripted_prompt(("demos", False), (None, False))
    else:
        # demos is disabled; quit immediately
        prompt = _scripted_prompt((None, False))
    tui.run(
        CARD,
        console=console,
        prompt=prompt,
        open_url=lambda _u: None,
        update_available=update_available,
        new_demos=new_demos,
    )
    return buf.getvalue()


def test_demos_enabled_shows_named_list():
    out = _demos_run(update_available=True, new_demos=[_ALPHA, _BETA])
    assert "New demos" in out
    assert "henry-castillo --update" in out
    assert "● alpha — does alpha" in out
    assert "● beta — does beta" in out


def test_demos_enabled_then_loop_continues():
    """Demos selected, then about, then quit — covers demos→loop-back branch."""
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(
            ("demos", False),  # enter demos block → loop back
            ("about", False),  # select about → renders
            (None, False),  # quit
        ),
        open_url=lambda _u: None,
        update_available=True,
        new_demos=[_ALPHA],
    )
    out = buf.getvalue()
    assert "New demos" in out
    assert "Bio." in out  # about was rendered after demos


def test_demos_disabled_when_no_update():
    """Demos choice is disabled when update_available=False."""
    console, _buf = _console()
    captured_choices: list[list[_Choice]] = []

    def _capture_prompt(
        _msg: str, choices: list[_Choice], _idx: int
    ) -> tuple[_Choice | None, bool]:
        captured_choices.append(list(choices))
        return (None, False)

    tui.run(
        CARD,
        console=console,
        prompt=_capture_prompt,
        open_url=lambda _u: None,
        update_available=False,
        new_demos=[_ALPHA],
    )
    demos_c = _choice("demos", captured_choices[0])
    assert demos_c.disabled is not None


def test_demos_disabled_when_no_new_demos():
    """Demos choice is disabled when new_demos is empty."""
    console, _buf = _console()
    captured_choices: list[list[_Choice]] = []

    def _capture_prompt(
        _msg: str, choices: list[_Choice], _idx: int
    ) -> tuple[_Choice | None, bool]:
        captured_choices.append(list(choices))
        return (None, False)

    tui.run(
        CARD,
        console=console,
        prompt=_capture_prompt,
        open_url=lambda _u: None,
        update_available=True,
        new_demos=[],
    )
    demos_c = _choice("demos", captured_choices[0])
    assert demos_c.disabled is not None


def test_demos_enabled_when_both_true():
    """Demos choice is enabled when update_available=True AND new_demos non-empty."""
    console, _buf = _console()
    captured_choices: list[list[_Choice]] = []

    def _capture_prompt(
        _msg: str, choices: list[_Choice], _idx: int
    ) -> tuple[_Choice | None, bool]:
        captured_choices.append(list(choices))
        return (None, False)

    tui.run(
        CARD,
        console=console,
        prompt=_capture_prompt,
        open_url=lambda _u: None,
        update_available=True,
        new_demos=[_ALPHA],
    )
    demos_c = _choice("demos", captured_choices[0])
    assert demos_c.disabled is None
    assert "1 new" in demos_c.label


def test_demos_markup_safe():
    """Rich markup in demo name/summary is shown literally (Text wrapping)."""
    markup_demo = Demo("[red]x[/red]", "[bold]y[/bold]", "0.9.0")
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("demos", False), (None, False)),
        open_url=lambda _u: None,
        update_available=True,
        new_demos=[markup_demo],
    )
    out = buf.getvalue()
    assert "[red]x[/red]" in out
    assert "[bold]y[/bold]" in out


def test_demos_default_new_demos_omitted():
    """Calling run without new_demos (default=()) -> demos choice disabled."""
    console, _buf = _console()
    captured_choices: list[list[_Choice]] = []

    def _capture_prompt(
        _msg: str, choices: list[_Choice], _idx: int
    ) -> tuple[_Choice | None, bool]:
        captured_choices.append(list(choices))
        return (None, False)

    tui.run(
        CARD,
        console=console,
        prompt=_capture_prompt,
        open_url=lambda _u: None,
        update_available=True,
        # new_demos deliberately omitted
    )
    demos_c = _choice("demos", captured_choices[0])
    assert demos_c.disabled is not None


# ---------------------------------------------------------------------------
# Cursor persistence — default_index threading
# ---------------------------------------------------------------------------


def test_cursor_persists_default_index():
    """After selecting 'resume' (index 2), next prompt call gets default_index=2."""
    prompt, calls = _recording_prompt(
        ("resume", False),  # select résumé (index 2 in choices)
        (None, False),
    )
    console, _buf = _console()
    tui.run(CARD, console=console, prompt=prompt, open_url=lambda _u: None)
    # First call: default_index=0; second call: default_index should be resume's index
    assert calls[0][2] == 0
    # Find the actual index of "resume" in the choices list passed in call 0
    resume_idx = next(i for i, c in enumerate(calls[0][1]) if c.id == "resume")
    assert calls[1][2] == resume_idx


# ---------------------------------------------------------------------------
# Choice order
# ---------------------------------------------------------------------------


def test_choice_order():
    captured: list[list[_Choice]] = []

    def _p(_msg: str, choices: list[_Choice], _idx: int) -> tuple[_Choice | None, bool]:
        captured.append(list(choices))
        return (None, False)

    tui.run(CARD, console=_console()[0], prompt=_p, open_url=lambda _u: None)
    ids = [c.id for c in captured[0]]
    expected = [
        "about",
        "projects",
        "resume",
        "contact",
        "blog",
        "twitter",
        "demos",
        "quit",
    ]
    assert ids == expected


# ---------------------------------------------------------------------------
# Projects submenu
# ---------------------------------------------------------------------------


def test_projects_submenu_back_returns():
    console, _buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(
            ("projects", False),  # enter submenu
            ("back", False),  # back from submenu
            (None, False),  # quit main
        ),
        open_url=lambda _u: None,
    )
    # No crash — returned normally


def test_projects_submenu_none_returns():
    console, _buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(
            ("projects", False),
            (None, False),  # None from submenu prompt -> return
            (None, False),  # quit main
        ),
        open_url=lambda _u: None,
    )


def test_projects_submenu_first_press_opens():
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(
            ("projects", False),  # enter submenu
            ("project:0", False),  # first press on p1 -> open
            ("back", False),  # back
            (None, False),  # quit main
        ),
        open_url=opened.append,
    )
    assert opened == ["https://example.com/p1"]
    assert "Opened in browser" in buf.getvalue()


def test_projects_submenu_stay_press_prints_url():
    opened: list[str] = []
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(
            ("projects", False),
            ("project:0", False),  # open + arm
            ("project:0", False),  # stay -> print URL
            ("back", False),
            (None, False),
        ),
        open_url=opened.append,
    )
    assert opened == ["https://example.com/p1"]  # only one open
    out = buf.getvalue()
    stripped_lines = [line.strip() for line in out.splitlines()]
    assert any(ln == "https://example.com/p1" for ln in stripped_lines)


def test_projects_submenu_move_away_and_back_reopens():
    opened: list[str] = []
    console, _buf = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(
            ("projects", False),
            ("project:0", False),  # open p1 + arm
            ("project:1", True),  # move to p2 -> open p2 + arm
            ("project:0", True),  # move back to p1 -> moved=True -> re-open p1
            ("back", False),
            (None, False),
        ),
        open_url=opened.append,
    )
    # p1 opened twice, p2 opened once
    assert opened.count("https://example.com/p1") == 2
    assert opened.count("https://example.com/p2") == 1


def test_projects_submenu_cursor_persistence():
    """default_index in submenu tracks the last selected project."""
    _, calls = _recording_prompt(
        ("projects", False),  # main: enter submenu
        ("project:1", False),  # submenu: pick project:1 (index 1)
        ("back", False),  # submenu: back
        (None, False),  # main: quit
    )
    # Re-build with recording prompt
    prompt, calls = _recording_prompt(
        ("projects", False),
        ("project:1", False),
        ("back", False),
        (None, False),
    )
    console, _buf = _console()
    tui.run(CARD, console=console, prompt=prompt, open_url=lambda _u: None)
    # calls[1] is first submenu call (default_index=0)
    # calls[2] is second submenu call (should be index of project:1)
    subm_choices = calls[1][1]
    proj1_idx = next(i for i, c in enumerate(subm_choices) if c.id == "project:1")
    assert calls[2][2] == proj1_idx


# ---------------------------------------------------------------------------
# Default open_url (webbrowser) when not injected
# ---------------------------------------------------------------------------


def test_default_open_url_uses_webbrowser(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(tui.webbrowser, "open", lambda u: calls.append(u) or True)
    tui._default_open_url("https://example.com")
    assert calls == ["https://example.com"]


def test_default_open_url_browser_error_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(url: str) -> None:
        raise webbrowser.Error("no browser")

    monkeypatch.setattr(tui.webbrowser, "open", _boom)
    tui._default_open_url("https://example.com")
    out = capsys.readouterr().out
    assert out.strip() == "Couldn't open a browser; visit https://example.com"


def test_default_open_url_os_error_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(url: str) -> None:
        raise OSError("exec failed")

    monkeypatch.setattr(tui.webbrowser, "open", _boom)
    tui._default_open_url("https://example.com")
    out = capsys.readouterr().out
    assert out.strip() == "Couldn't open a browser; visit https://example.com"


def test_run_uses_default_open_url_when_not_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(tui.webbrowser, "open", lambda u: calls.append(u) or True)
    console, _ = _console()
    tui.run(
        CARD,
        console=console,
        prompt=_scripted_prompt(("blog", False), (None, False)),
    )
    assert calls == ["https://s.substack.com"]


def test_run_uses_default_prompt_when_not_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """default_prompt returns (None, False) immediately -> loop exits after banner."""
    monkeypatch.setattr(tui, "_default_prompt", lambda *_a, **_k: (None, False))
    console, buf = _console()
    tui.run(CARD, console=console)
    assert "Henry Castillo" in buf.getvalue()


# ===========================================================================
# Layer 1 — _render_menu direct tests (covers every token branch)
# ===========================================================================


def test_render_menu_selected_row() -> None:
    choices = [_Choice("a", "Alpha"), _Choice("b", "Beta")]
    ft = _render_menu("msg", choices, 0)
    text = "".join(item[1] for item in ft)
    assert "❯ Alpha" in text


def test_render_menu_unselected_row() -> None:
    choices = [_Choice("a", "Alpha"), _Choice("b", "Beta")]
    ft = _render_menu("msg", choices, 0)
    text = "".join(item[1] for item in ft)
    assert "  Beta" in text  # unselected row has two spaces


def test_render_menu_disabled_row() -> None:
    choices = [
        _Choice("a", "Alpha"),
        _Choice("d", "Disabled item", disabled="under construction"),
    ]
    ft = _render_menu("msg", choices, 0)
    styles = [item[0] for item in ft]
    combined = "".join(item[1] for item in ft)
    assert "Disabled item" in combined
    assert "under construction" in combined
    # disabled row uses class:disabled token
    assert any("disabled" in s for s in styles)


# ===========================================================================
# Layer 1 — _next_enabled direct tests (covers skip-disabled + clamp)
# ===========================================================================


def test_next_enabled_skips_disabled_down() -> None:
    choices = [
        _Choice("a", "A"),
        _Choice("d", "D", disabled="x"),
        _Choice("b", "B"),
    ]
    assert _next_enabled(choices, 0, 1) == 2  # skips index 1


def test_next_enabled_skips_disabled_up() -> None:
    choices = [
        _Choice("a", "A"),
        _Choice("d", "D", disabled="x"),
        _Choice("b", "B"),
    ]
    assert _next_enabled(choices, 2, -1) == 0  # skips index 1


def test_next_enabled_clamps_at_top() -> None:
    choices = [_Choice("a", "A"), _Choice("b", "B")]
    assert _next_enabled(choices, 0, -1) == 0  # already at top


def test_next_enabled_clamps_at_bottom() -> None:
    choices = [_Choice("a", "A"), _Choice("b", "B")]
    assert _next_enabled(choices, 1, 1) == 1  # already at bottom


def test_next_enabled_all_disabled_above() -> None:
    choices = [
        _Choice("d", "D", disabled="x"),
        _Choice("b", "B"),
    ]
    assert _next_enabled(choices, 1, -1) == 1  # can't move up, clamp


# ===========================================================================
# Layer 2 — pure handler unit tests
#
# We test the handlers directly (no asyncio / no socket / no terminal).
# ===========================================================================

# Simple choices for handler tests
_C_A = _Choice("a", "Alpha")
_C_B = _Choice("b", "Beta")
_C_C = _Choice("c", "Gamma")
_C_DIS = _Choice("dis", "Disabled", disabled="reason")


# ---------------------------------------------------------------------------
# _PromptState initial state
# ---------------------------------------------------------------------------


def test_prompt_state_default_result() -> None:
    """_PromptState initializes result to (None, False)."""
    state = tui._PromptState(index=0)
    assert state.result == (None, False)
    assert state.moved is False


# ---------------------------------------------------------------------------
# _handle_up / _handle_down
# ---------------------------------------------------------------------------


def test_handle_down_moves_and_sets_moved() -> None:
    state = tui._PromptState(index=0)
    tui._handle_down(state, [_C_A, _C_B])
    assert state.index == 1
    assert state.moved is True


def test_handle_down_clamps_at_bottom() -> None:
    state = tui._PromptState(index=1)
    tui._handle_down(state, [_C_A, _C_B])
    assert state.index == 1
    assert state.moved is False  # clamped — no change


def test_handle_up_moves_and_sets_moved() -> None:
    state = tui._PromptState(index=1)
    tui._handle_up(state, [_C_A, _C_B])
    assert state.index == 0
    assert state.moved is True


def test_handle_up_clamps_at_top() -> None:
    state = tui._PromptState(index=0)
    tui._handle_up(state, [_C_A, _C_B])
    assert state.index == 0
    assert state.moved is False  # clamped


def test_handle_down_skips_disabled() -> None:
    """Down skips a disabled item in the middle."""
    state = tui._PromptState(index=0)
    tui._handle_down(state, [_C_A, _C_DIS, _C_B])
    assert state.index == 2  # jumped over index 1
    assert state.moved is True


def test_handle_up_skips_disabled() -> None:
    """Up skips a disabled item in the middle."""
    state = tui._PromptState(index=2)
    tui._handle_up(state, [_C_A, _C_DIS, _C_B])
    assert state.index == 0
    assert state.moved is True


# ---------------------------------------------------------------------------
# _handle_enter
# ---------------------------------------------------------------------------


def test_handle_enter_enabled_sets_result_and_returns_true() -> None:
    state = tui._PromptState(index=0)
    exited = tui._handle_enter(state, [_C_A, _C_B])
    assert exited is True
    assert state.result == (_C_A, False)


def test_handle_enter_enabled_with_moved() -> None:
    state = tui._PromptState(index=1, moved=True)
    exited = tui._handle_enter(state, [_C_A, _C_B])
    assert exited is True
    assert state.result == (_C_B, True)


def test_handle_enter_disabled_does_nothing() -> None:
    """Enter on a disabled item is ignored (returns False, no result set)."""
    state = tui._PromptState(index=0)
    exited = tui._handle_enter(state, [_C_DIS, _C_B])
    assert exited is False
    assert state.result == (None, False)  # unchanged default


# ---------------------------------------------------------------------------
# _handle_quit
# ---------------------------------------------------------------------------


def test_handle_quit_sets_none_result() -> None:
    state = tui._PromptState(index=0)
    tui._handle_quit(state)
    assert state.result == (None, False)


def test_handle_quit_preserves_moved() -> None:
    state = tui._PromptState(index=1, moved=True)
    tui._handle_quit(state)
    assert state.result == (None, True)


def test_render_menu_disabled_row_when_selected_index() -> None:
    """A disabled item at the current index still renders as disabled."""
    choices = [_C_DIS, _C_A]
    ft = _render_menu("msg", choices, 0)
    styles = [item[0] for item in ft]
    assert any("disabled" in s for s in styles)


# ===========================================================================
# Layer 2 — _default_prompt + _make_prompt_app integration
# ===========================================================================


def test_default_prompt_state_field_defaults() -> None:
    """_PromptState.result field_default yields (None, False), not a shared object."""
    s1 = tui._PromptState(index=0)
    s2 = tui._PromptState(index=1)
    # Mutate s1 to confirm it doesn't affect s2 (field_factory isolation)
    s1.result = (_C_A, True)
    assert s2.result == (None, False)


def test_make_prompt_app_get_text_callable() -> None:
    """_make_prompt_app returns an Application whose layout renders the menu.

    We extract the text getter from the FormattedTextControl and invoke it
    directly — this covers the _get_text closure inside _make_prompt_app.
    """
    choices = [_C_A, _C_B]
    state = tui._PromptState(index=0)
    app = tui._make_prompt_app("test msg", choices, state)
    # The layout is: Layout(Window(content=FormattedTextControl(callable)))
    window = app.layout.container  # type: ignore[union-attr]
    control = window.content  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]
    # Get the underlying callable (the _get_text closure)
    ft = control.text()  # type: ignore[operator]
    text = "".join(item[1] for item in ft)
    assert "❯ Alpha" in text
    assert "test msg" in text


def _get_key_handlers(
    choices: list[_Choice],
    state: tui._PromptState,
) -> dict[str, Callable[..., object]]:
    """Build _make_prompt_app and extract handlers by key string."""
    app = tui._make_prompt_app("msg", choices, state)
    result: dict[str, Callable[..., object]] = {}
    for b in app.key_bindings.bindings:  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]
        result[str(b.keys[0])] = b.handler
    return result


class _MockEvent:
    """Minimal fake prompt_toolkit event with app.exit() tracking."""

    def __init__(self) -> None:
        self.exited = False

    @property
    def app(self) -> object:
        return self

    def exit(self) -> None:
        self.exited = True


def test_make_prompt_app_up_handler_moves_cursor() -> None:
    """The up-arrow key handler calls _handle_up (covers line 163)."""
    choices = [_C_A, _C_B]
    state = tui._PromptState(index=1)
    handlers = _get_key_handlers(choices, state)
    event = _MockEvent()
    handlers["Keys.Up"](event)
    assert state.index == 0
    assert state.moved is True


def test_make_prompt_app_down_handler_moves_cursor() -> None:
    """The down-arrow key handler calls _handle_down (covers line 168)."""
    choices = [_C_A, _C_B]
    state = tui._PromptState(index=0)
    handlers = _get_key_handlers(choices, state)
    event = _MockEvent()
    handlers["Keys.Down"](event)
    assert state.index == 1
    assert state.moved is True


def test_make_prompt_app_enter_handler_exits_on_enabled() -> None:
    """Enter on an enabled item sets result and calls app.exit()."""
    choices = [_C_A, _C_B]
    state = tui._PromptState(index=0)
    handlers = _get_key_handlers(choices, state)
    event = _MockEvent()
    handlers["Keys.ControlM"](event)
    assert state.result == (_C_A, False)
    assert event.exited is True


def test_make_prompt_app_enter_handler_ignores_disabled() -> None:
    """Enter on disabled item: does NOT call app.exit() (False branch)."""
    choices = [_C_DIS, _C_B]
    state = tui._PromptState(index=0)
    handlers = _get_key_handlers(choices, state)
    event = _MockEvent()
    handlers["Keys.ControlM"](event)
    assert state.result == (None, False)  # unchanged
    assert event.exited is False  # app.exit was NOT called


def test_make_prompt_app_quit_handler_sets_result_and_exits() -> None:
    """q / ctrl-c / ctrl-d set result and exit (covers 179-180)."""
    choices = [_C_A, _C_B]
    state = tui._PromptState(index=0)
    handlers = _get_key_handlers(choices, state)
    event = _MockEvent()
    handlers["q"](event)
    assert state.result == (None, False)
    assert event.exited is True


def test_default_prompt_via_monkeypatched_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_default_prompt's .run() call is covered by patching _make_prompt_app.

    The fake makes run() call _handle_enter, exercising the full
    _default_prompt body (state creation, _make_prompt_app, .run(), return).
    """
    choices = [_C_A, _C_B]

    # Capture the state that _make_prompt_app receives so we can mutate it
    captured_state: list[tui._PromptState] = []

    def _fake_make(message: str, ch: list[_Choice], st: tui._PromptState) -> object:
        captured_state.append(st)

        # Return a fake app whose .run() simulates pressing enter
        class _FakeApp:
            def run(self) -> None:
                tui._handle_enter(st, ch)

        return _FakeApp()

    monkeypatch.setattr(tui, "_make_prompt_app", _fake_make)
    result = tui._default_prompt("msg", choices, 0)
    assert result == (_C_A, False)
    assert len(captured_state) == 1
    assert captured_state[0].index == 0


# ===========================================================================
# Layer 2 — real prompt_toolkit Application end-to-end tests
#
# These tests run the ACTUAL Application.run() event loop via piped key input.
# The autouse _block_network fixture in conftest.py patches socket.socket,
# which breaks asyncio's internal socketpair() used by the event loop.
# The _allow_asyncio_loop fixture below restores a working socketpair so the
# real event loop can start, while keeping the network-blocking patch intact.
# ===========================================================================


@pytest.fixture
def _allow_asyncio_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore a working socketpair so asyncio's event loop can start.

    The autouse _block_network fixture replaces socket.socket with a function
    that raises, which causes asyncio's internal socketpair() call (used to
    wake up the selector) to fail.  We replace socketpair with an
    implementation that calls the *real* C-level _socket.socketpair and wraps
    the resulting file-descriptors with real C-level _socket.socket objects.

    create_pipe_input() uses os.pipe() internally (not sockets), so only the
    event-loop socketpair needs restoring — the network block remains in effect.
    Note: we use _socket.socket (the C-level class) directly rather than
    _socket_mod.socket, because the autouse fixture patches _socket_mod.socket
    to a _deny function before this fixture runs.
    """

    def _fixed_socketpair(
        family: int = _socket_mod.AF_UNIX,
        sock_type: int = _socket_mod.SOCK_STREAM,
        proto: int = 0,
    ) -> tuple[_socket.socket, _socket.socket]:
        a, b = _socket.socketpair(family, sock_type, proto)
        return (
            _socket.socket(family, sock_type, proto, a.detach()),
            _socket.socket(family, sock_type, proto, b.detach()),
        )

    monkeypatch.setattr(_socket_mod, "socketpair", _fixed_socketpair)


def _run_real_app(
    key_input: str,
    choices: list[_Choice],
    default_index: int = 0,
) -> tuple[_Choice | None, bool]:
    """Run _default_prompt through the real Application event loop.

    Uses a PipeInput (os.pipe-based, not socket-based) and DummyOutput so the
    test is hermetic — no terminal, no network.
    """
    with create_pipe_input() as inp:
        inp.send_text(key_input)
        with create_app_session(input=inp, output=DummyOutput()):
            return tui._default_prompt("Test menu", choices, default_index)


# ---------------------------------------------------------------------------
# Real-app test: enter with no navigation
# ---------------------------------------------------------------------------


def test_real_app_enter_no_move(_allow_asyncio_loop: None) -> None:
    """\\r at default_index=0 returns (choices[0], moved=False)."""
    choices = [_C_A, _C_B, _C_C]
    result = _run_real_app("\r", choices, default_index=0)
    assert result == (_C_A, False)


# ---------------------------------------------------------------------------
# Real-app test: down then enter
# ---------------------------------------------------------------------------


def test_real_app_down_enter(_allow_asyncio_loop: None) -> None:
    """\\x1b[B\\r (down, enter) returns (next enabled choice, moved=True)."""
    choices = [_C_A, _C_B, _C_C]
    result = _run_real_app("\x1b[B\r", choices, default_index=0)
    assert result == (_C_B, True)


# ---------------------------------------------------------------------------
# Real-app test: down then up then enter (navigate away and back)
# ---------------------------------------------------------------------------


def test_real_app_down_up_enter(_allow_asyncio_loop: None) -> None:
    """\\x1b[B\\x1b[A\\r goes down then up, ending at choices[0] with moved=True."""
    choices = [_C_A, _C_B, _C_C]
    result = _run_real_app("\x1b[B\x1b[A\r", choices, default_index=0)
    # Back at original index, but moved flag is True (navigated away and back)
    assert result == (_C_A, True)


# ---------------------------------------------------------------------------
# Real-app test: disabled item is skipped during navigation
# ---------------------------------------------------------------------------


def test_real_app_skips_disabled_item(_allow_asyncio_loop: None) -> None:
    """Down arrow skips a disabled item and lands on the next enabled choice."""
    choices = [_C_A, _C_DIS, _C_B]
    result = _run_real_app("\x1b[B\r", choices, default_index=0)
    # Index 1 is disabled — should jump straight to index 2 (_C_B)
    assert result == (_C_B, True)
    assert result[0] is not _C_DIS


# ---------------------------------------------------------------------------
# Real-app test: quit keys
# ---------------------------------------------------------------------------


def test_real_app_q_quits(_allow_asyncio_loop: None) -> None:
    """'q' exits and returns (None, _)."""
    choices = [_C_A, _C_B]
    choice, _moved = _run_real_app("q", choices)
    assert choice is None


def test_real_app_ctrl_c_quits(_allow_asyncio_loop: None) -> None:
    """Ctrl-C (\\x03) exits and returns (None, _)."""
    choices = [_C_A, _C_B]
    choice, _moved = _run_real_app("\x03", choices)
    assert choice is None


def test_real_app_ctrl_d_quits(_allow_asyncio_loop: None) -> None:
    """Ctrl-D (\\x04) exits and returns (None, _)."""
    choices = [_C_A, _C_B]
    choice, _moved = _run_real_app("\x04", choices)
    assert choice is None


# ---------------------------------------------------------------------------
# Real-app test: vi j/k bindings
# ---------------------------------------------------------------------------


def test_real_app_vi_j_moves_down(_allow_asyncio_loop: None) -> None:
    """'j' (vi down binding) moves cursor down one enabled item."""
    choices = [_C_A, _C_B, _C_C]
    result = _run_real_app("j\r", choices, default_index=0)
    assert result == (_C_B, True)


def test_real_app_vi_k_moves_up(_allow_asyncio_loop: None) -> None:
    """'k' (vi up binding) moves cursor up one enabled item."""
    choices = [_C_A, _C_B, _C_C]
    result = _run_real_app("k\r", choices, default_index=1)
    assert result == (_C_A, True)
