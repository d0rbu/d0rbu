import socket
import urllib.request

import pytest


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
