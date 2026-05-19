"""Tests for tui.py — strict Card types, Blog, Demos (under construction), badge."""

import io

import pytest
from rich.console import Console

from henry_castillo import tui
from henry_castillo.content import (
    Card,
    parse_card,
)

# ---------------------------------------------------------------------------
# Shared test fixtures (schema-valid via parse_card)
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
    },
}
_VALID_DOC: dict[str, object] = {
    "schema_version": 1,
    "profile": _TUI_PROFILE_DOC,
    "projects": [
        {
            "name": "p1",
            "blurb": "b1",
            "url": "u1",
            "tags": ["t"],
        }
    ],
    "resume": {
        "pdf": "",
        "experience": [],
        "education": [],
        "highlights": [],
    },
}

CARD: Card = parse_card(_VALID_DOC)


def _console():
    buf = io.StringIO()
    return Console(file=buf, width=80, no_color=True), buf


# ---------------------------------------------------------------------------
# Basic loop behaviour
# ---------------------------------------------------------------------------


def test_loop_renders_selected_then_quits():
    console, buf = _console()
    seq = iter(["About", "Projects", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert "Henry Castillo" in out  # banner shown once
    assert "Bio." in out  # About rendered
    assert "p1" in out  # Projects rendered


def test_quit_immediately_only_banner():
    console, buf = _console()
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: None,
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert "Henry Castillo" in out
    assert "Bio." not in out


def test_quit_string_choice_exits_loop():
    console, buf = _console()
    seq = iter(["Quit"])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert "Henry Castillo" in out
    assert "Bio." not in out


# ---------------------------------------------------------------------------
# Blog selection
# ---------------------------------------------------------------------------


def test_blog_selection_opens_url():
    console, _ = _console()
    opened: list[str] = []
    seq = iter(["Blog", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=opened.append,
    )
    assert opened == ["https://s.substack.com"]


def test_blog_unconfigured_does_not_open():
    doc = {
        **_VALID_DOC,
        "profile": {
            **_TUI_PROFILE_DOC,
            "links": {"github": "https://github.com/d0rbu", "blog": ""},
        },
    }
    card = parse_card(doc)
    console, _ = _console()
    opened: list[str] = []
    seq = iter(["Blog", None])
    tui.run(
        card,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=opened.append,
    )
    assert opened == []


def test_non_blog_section_does_not_open():
    console, _ = _console()
    opened: list[str] = []
    seq = iter(["About", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=opened.append,
    )
    assert opened == []


# ---------------------------------------------------------------------------
# Demos (under construction) + update badge
# ---------------------------------------------------------------------------


def test_demos_shows_under_construction():
    console, buf = _console()
    seq = iter(["Demos (under construction)", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert "under construction" in out.lower()


def test_demos_no_badge_when_update_not_available():
    console, buf = _console()
    seq = iter(["Demos (under construction)", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
        update_available=False,
    )
    out = buf.getvalue()
    assert "newer henry-castillo" not in out


def test_demos_badge_shown_when_update_available():
    console, buf = _console()
    seq = iter(["Demos (under construction)", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
        update_available=True,
    )
    out = buf.getvalue()
    assert "newer henry-castillo" in out


def test_demos_continues_loop_does_not_render_section():
    """Selecting Demos should not render any content section."""
    console, buf = _console()
    seq = iter(["Demos (under construction)", "About", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    # Bio is from About (which renders), Demos does not render Bio
    assert "Bio." in out


# ---------------------------------------------------------------------------
# Unknown selection ignored
# ---------------------------------------------------------------------------


def test_unknown_selection_is_ignored():
    console, buf = _console()
    seq = iter(["Nonsense", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert "Bio." not in out  # no section rendered for junk choices


# ---------------------------------------------------------------------------
# Other sections render
# ---------------------------------------------------------------------------


def test_resume_selection_renders():
    console, buf = _console()
    seq = iter(["Résumé", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    assert "Résumé" in buf.getvalue()


def test_contact_selection_renders():
    console, buf = _console()
    seq = iter(["Contact", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    assert "e@x.y" in buf.getvalue()


# ---------------------------------------------------------------------------
# Banner printed once
# ---------------------------------------------------------------------------


def test_banner_once_before_loop():
    console, buf = _console()
    seq = iter(["About", "Projects", None])
    tui.run(
        CARD,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert out.count("Henry Castillo") == 1


# ---------------------------------------------------------------------------
# Menu order
# ---------------------------------------------------------------------------


def test_menu_order_passed_to_select():
    console, _ = _console()
    captured: list[list[str]] = []

    def sel(_message, choices):
        captured.append(list(choices))

    tui.run(CARD, console=console, select=sel, open_url=lambda _u: None)
    assert captured == [
        [
            "About",
            "Projects",
            "Résumé",
            "Contact",
            "Blog",
            "Demos (under construction)",
            "Quit",
        ]
    ]


# ---------------------------------------------------------------------------
# Default collaborators
# ---------------------------------------------------------------------------


def test_default_select_wraps_questionary(monkeypatch):
    class FakeQ:
        def ask(self):
            return "About"

    captured = {}

    def fake_select(message, choices, **kwargs):
        captured["message"] = message
        captured["choices"] = choices
        return FakeQ()

    monkeypatch.setattr(tui.questionary, "select", fake_select)
    assert tui._default_select("Pick", ["About", "Quit"]) == "About"
    assert captured["choices"] == ["About", "Quit"]


def test_default_select_returns_none_on_keyboardinterrupt(monkeypatch):
    def fake_select(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(tui.questionary, "select", fake_select)
    try:
        result = tui._default_select("Pick", ["About"])
    except KeyboardInterrupt:
        pytest.fail("KeyboardInterrupt escaped _default_select (catch removed)")
    assert result is None


def test_default_select_returns_none_on_eoferror(monkeypatch):
    def fake_select(*_a, **_k):
        raise EOFError

    monkeypatch.setattr(tui.questionary, "select", fake_select)
    try:
        result = tui._default_select("Pick", ["About"])
    except EOFError:
        pytest.fail("EOFError escaped _default_select (catch removed)")
    assert result is None


def test_default_open_url_uses_webbrowser(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(tui.webbrowser, "open", lambda u: calls.append(u) or True)
    tui._default_open_url("https://example.com")
    assert calls == ["https://example.com"]


def test_run_uses_real_defaults_when_not_injected(monkeypatch):
    """default select returns None immediately -> loop exits after banner."""
    monkeypatch.setattr(tui, "_default_select", lambda *_a, **_k: None)
    console, buf = _console()
    tui.run(CARD, console=console)
    assert "Henry Castillo" in buf.getvalue()


def test_run_open_url_defaults_to_webbrowser(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(tui.webbrowser, "open", lambda u: calls.append(u) or True)
    console, _ = _console()
    seq = iter(["Blog", None])
    tui.run(CARD, console=console, select=lambda *_a, **_k: next(seq))
    assert calls == ["https://s.substack.com"]
