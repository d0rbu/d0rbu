import io
import os
import time

from rich.console import Console

from henry_castillo import failure_ui as F  # noqa: N812


def _con() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=80, no_color=True), buf


def test_non_tty_prints_stderr_and_returns_1(capsys):
    console, _ = _con()
    rc = F.show_no_data(
        "boom-msg",
        url="https://d0rbu.github.io/d0rbu/",
        is_tty=False,
        console=console,
        wait_for_keypress=lambda _t: True,
        open_url=lambda _u: None,
        sleep=lambda _s: None,
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "boom-msg" in err
    assert "henryandrecastillo@gmail.com" in err


def test_tty_keypress_exits_without_opening():
    console, buf = _con()
    opened: list[str] = []
    rc = F.show_no_data(
        "boom-msg",
        url="U",
        is_tty=True,
        console=console,
        wait_for_keypress=lambda _t: True,
        open_url=opened.append,
        sleep=lambda _s: None,
    )
    assert rc == 0
    assert opened == []
    out = buf.getvalue()
    assert "boom-msg" in out
    assert "press any key to exit" in out


def test_tty_timeout_opens_url():
    console, buf = _con()
    opened: list[str] = []
    rc = F.show_no_data(
        "boom-msg",
        url="https://site",
        is_tty=True,
        console=console,
        wait_for_keypress=lambda _t: False,
        open_url=opened.append,
        sleep=lambda _s: None,
    )
    assert rc == 0
    assert opened == ["https://site"]
    out = buf.getvalue()
    for n in ("5", "4", "3", "2", "1"):
        assert n in out


def test_tty_keypress_on_third_second():
    console, _ = _con()
    opened: list[str] = []
    seq = iter([False, False, True])
    rc = F.show_no_data(
        "m",
        url="U",
        is_tty=True,
        console=console,
        wait_for_keypress=lambda _t: next(seq),
        open_url=opened.append,
        sleep=lambda _s: None,
    )
    assert rc == 0 and opened == []


def test_tty_default_sleep_used_when_not_injected():
    # Do NOT inject sleep -> the real time.sleep default is exercised
    # (wait_for_keypress False all 5 -> loop sleeps via the real default).
    console, _ = _con()
    opened: list[str] = []
    start = time.monotonic()
    rc = F.show_no_data(
        "m",
        url="U",
        is_tty=True,
        console=console,
        wait_for_keypress=lambda _t: False,
        open_url=opened.append,
    )
    assert rc == 0 and opened == ["U"]
    assert time.monotonic() - start < 5.0  # default sleep is sleep(0), instant


def test_default_open_url_uses_webbrowser(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(F.webbrowser, "open", lambda u: calls.append(u) or True)
    F._default_open_url("https://example.com")
    assert calls == ["https://example.com"]


def test_default_wait_for_keypress_timeout_false():
    primary, secondary = os.openpty()
    try:
        assert F._default_wait_for_keypress(0.05, stream_fd=secondary) is False
    finally:
        os.close(primary)
        os.close(secondary)


def test_default_wait_for_keypress_key_true():
    primary, secondary = os.openpty()
    try:
        os.write(primary, b"x")
        time.sleep(0.02)
        assert F._default_wait_for_keypress(1.0, stream_fd=secondary) is True
    finally:
        os.close(primary)
        os.close(secondary)


def test_show_no_data_uses_real_defaults_path(monkeypatch):
    # is_tty True, inject nothing except a keypress-true so it returns fast,
    # exercising the `wait_for_keypress or _default_wait_for_keypress` and
    # `open_url or _default_open_url` default-binding lines.
    console, _ = _con()
    monkeypatch.setattr(F, "_default_wait_for_keypress", lambda _t: True)
    rc = F.show_no_data("m", url="U", is_tty=True, console=console)
    assert rc == 0
