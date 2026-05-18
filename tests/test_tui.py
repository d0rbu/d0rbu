import io

from rich.console import Console

from henry_castillo import tui
from henry_castillo.content import Profile, Project

PROFILE = Profile(
    name="Henry Castillo",
    handle="d0rbu",
    tagline="ML",
    about="Bio.",
    email="e@x.y",
    links={"github": "https://github.com/d0rbu", "substack": "https://s.substack.com"},
)
PROJECTS = [Project("p1", "b1", "u1", ["t"])]


def _console():
    buf = io.StringIO()
    return Console(file=buf, width=80, no_color=True), buf


def test_loop_renders_selected_then_quits():
    console, buf = _console()
    seq = iter(["About", "Projects", None])  # None => quit
    tui.run(
        PROFILE,
        PROJECTS,
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
        PROFILE,
        PROJECTS,
        console=console,
        select=lambda *_a, **_k: None,
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert "Henry Castillo" in out
    assert "Bio." not in out


def test_substack_selection_opens_url():
    console, _ = _console()
    opened: list[str] = []
    seq = iter(["Substack", None])
    tui.run(
        PROFILE,
        PROJECTS,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=opened.append,
    )
    assert opened == ["https://s.substack.com"]


def test_substack_unconfigured_does_not_open():
    console, _ = _console()
    opened: list[str] = []
    seq = iter(["Substack", None])
    tui.run(
        Profile(name="N"),
        PROJECTS,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=opened.append,
    )
    assert opened == []


def test_unknown_selection_is_ignored():
    console, buf = _console()
    seq = iter(["Lab (locked)", "Nonsense", None])
    tui.run(
        PROFILE,
        PROJECTS,
        console=console,
        select=lambda *_a, **_k: next(seq),
        open_url=lambda _u: None,
    )
    out = buf.getvalue()
    assert "locked" in out.lower()  # informs the user Lab is unavailable
    assert "Bio." not in out  # no section rendered for junk choices


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
    assert tui._default_select("Pick", ["About"]) is None


def test_default_open_url_uses_webbrowser(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(tui.webbrowser, "open", lambda u: calls.append(u) or True)
    tui._default_open_url("https://example.com")
    assert calls == ["https://example.com"]


def test_run_uses_real_defaults_when_not_injected(monkeypatch):
    # default select returns None immediately -> loop exits after banner
    monkeypatch.setattr(tui, "_default_select", lambda *_a, **_k: None)
    console, buf = _console()
    tui.run(PROFILE, PROJECTS, console=console)
    assert "Henry Castillo" in buf.getvalue()
