import json
from pathlib import Path

from henry_castillo import update


def test_is_outdated_true_and_false():
    assert update.is_outdated("0.1.0", "0.2.0") is True
    assert update.is_outdated("1.0.0", "1.0.0") is False
    assert update.is_outdated("2.0.0", "1.9.9") is False


def test_is_outdated_handles_garbage():
    assert update.is_outdated("0.1.0", "not-a-version") is False


def test_fetch_latest_version_parses_payload(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"info": {"version": "9.9.9"}}'

    monkeypatch.setattr(update.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    assert update.fetch_latest_version(url="https://example/x") == "9.9.9"


def test_fetch_latest_version_returns_none_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(update.urllib.request, "urlopen", boom)
    assert update.fetch_latest_version(url="https://example/x") is None


def test_check_for_update_uses_cache_and_throttles(tmp_path: Path):
    cache = tmp_path / "u.json"
    calls = []

    def fetcher():
        calls.append(1)
        return "9.9.9"

    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=fetcher
    )
    assert got == "9.9.9"
    assert len(calls) == 1
    got2 = update.check_for_update(
        now=1050.0, cache_path=cache, interval=100, fetcher=fetcher
    )
    assert got2 == "9.9.9"
    assert len(calls) == 1
    assert json.loads(cache.read_text())["latest"] == "9.9.9"


def test_check_for_update_none_when_current(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "9.9.9")
    got = update.check_for_update(
        now=1.0,
        cache_path=tmp_path / "u.json",
        interval=0,
        fetcher=lambda: "9.9.9",
    )
    assert got is None


def test_check_for_update_fetcher_returns_none_keeps_existing(tmp_path: Path):
    """When fetcher returns None, existing cached latest is preserved."""
    cache = tmp_path / "u.json"
    # Prime cache with an old check time so re-fetch is triggered, but fetcher fails.
    cache.write_text('{"last_check": 0, "latest": null}')
    got = update.check_for_update(
        now=1000.0,
        cache_path=cache,
        interval=100,
        fetcher=lambda: None,
    )
    # latest was null/None in cache and fetcher returned None -> no update
    assert got is None


def test_update_notice_contains_version_and_flag():
    """update_notice must mention the latest version and the --update flag."""
    msg = update.update_notice("9.9.9")
    assert "9.9.9" in msg
    assert "--update" in msg


def test_cache_path_returns_path():
    """cache_path() must return a Path under a henry-castillo subdirectory."""
    p = update.cache_path()
    assert isinstance(p, Path)
    assert "henry-castillo" in str(p)


def test_cache_path_respects_xdg(monkeypatch, tmp_path):
    """cache_path() uses XDG_CACHE_HOME when set."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = update.cache_path()
    assert str(p).startswith(str(tmp_path))


def test_perform_update_uses_uv(monkeypatch):
    """When uv is on PATH, perform_update should call uv tool upgrade."""
    commands_called = []

    def fake_which_uv(x):
        return "/usr/bin/uv" if x == "uv" else None

    monkeypatch.setattr(update.shutil, "which", fake_which_uv)
    monkeypatch.setattr(
        update.subprocess, "call", lambda cmd: commands_called.append(cmd) or 0
    )
    rc = update.perform_update()
    assert rc == 0
    assert commands_called[0][0] == "uv"
    assert "upgrade" in commands_called[0]


def test_perform_update_uses_pipx(monkeypatch):
    """When uv is absent but pipx is on PATH, perform_update calls pipx upgrade."""
    commands_called = []

    def fake_which_pipx(x):
        return "/usr/bin/pipx" if x == "pipx" else None

    monkeypatch.setattr(update.shutil, "which", fake_which_pipx)
    monkeypatch.setattr(
        update.subprocess, "call", lambda cmd: commands_called.append(cmd) or 0
    )
    rc = update.perform_update()
    assert rc == 0
    assert commands_called[0][0] == "pipx"
    assert "upgrade" in commands_called[0]


def test_perform_update_falls_back_to_pip(monkeypatch):
    """When neither uv nor pipx are available, perform_update falls back to pip."""
    commands_called = []
    monkeypatch.setattr(update.shutil, "which", lambda x: None)
    monkeypatch.setattr(
        update.subprocess, "call", lambda cmd: commands_called.append(cmd) or 0
    )
    rc = update.perform_update()
    assert rc == 0
    assert "pip" in " ".join(commands_called[0])
    assert "install" in commands_called[0]
    assert "--upgrade" in commands_called[0]
