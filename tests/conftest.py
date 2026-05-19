import socket
import urllib.request

import pytest

import henry_castillo.__main__ as _main_mod


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _deny(*args, **kwargs):
        raise RuntimeError("Real network access is blocked in tests")

    monkeypatch.setattr(urllib.request, "urlopen", _deny)
    monkeypatch.setattr(socket, "socket", _deny)


@pytest.fixture(autouse=True)
def _env_hygiene(monkeypatch):
    monkeypatch.delenv("HENRY_CASTILLO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("LINES", raising=False)


@pytest.fixture
def stub_tui_run(monkeypatch):
    """Replace the interactive loop with a silent no-op so a tty-default
    main([]) does not enter questionary under pytest."""
    monkeypatch.setattr(_main_mod.tui, "run", lambda *_a, **_k: None)
