"""Exhaustive behavioral tests for henry_castillo.update.

Every branch is proven by behavior (not merely executed). The two latent
bugs (non-dict cache crash; non-string PyPI version coercion) have explicit
regression tests. No real network is used (see tests/conftest.py).
"""

import json
import sys
import urllib.error
from email.message import Message
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import henry_castillo
from henry_castillo import update

# ---------------------------------------------------------------------------
# is_outdated — PEP 440 matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        # equal
        ("1.0.0", "1.0.0", False),
        # pre-release vs final, both directions
        ("1.0.0rc1", "1.0.0", True),
        ("1.0.0", "1.0.0rc1", False),
        # post-release
        ("1.0.0", "1.0.0.post1", True),
        ("1.0.0.post1", "1.0.0", False),
        # dev, both directions
        ("1.0.0.dev1", "1.0.0", True),
        ("1.0.0", "1.0.0.dev1", False),
        # local version segment (pin current behavior: build local IS "newer")
        ("1.0.0", "1.0.0+build.5", True),
        ("1.0.0+build.5", "1.0.0", False),
        # leading v is tolerated by packaging
        ("v1.0.0", "v1.1.0", True),
        ("v1.1.0", "v1.0.0", False),
        # epoch
        ("1.0.0", "1!0.1.0", True),
        ("1!0.1.0", "1.0.0", False),
        # ordinary newer / older
        ("0.1.0", "0.2.0", True),
        ("2.0.0", "1.9.9", False),
        # invalid current -> False
        ("not-a-version", "1.0.0", False),
        # invalid latest -> False
        ("1.0.0", "not-a-version", False),
        # empty strings -> False
        ("", "1.0.0", False),
        ("1.0.0", "", False),
        ("", "", False),
    ],
)
def test_is_outdated_matrix(current, latest, expected):
    assert update.is_outdated(current, latest) is expected


# ---------------------------------------------------------------------------
# fetch_latest_version — happy path + full error matrix
# ---------------------------------------------------------------------------


def _fake_resp(body: bytes):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return body

    return FakeResp()


def test_fetch_latest_version_happy_path_passes_url_and_timeout(monkeypatch):
    captured = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return _fake_resp(b'{"info": {"version": "9.9.9"}}')

    monkeypatch.setattr(update.urllib.request, "urlopen", fake_urlopen)
    got = update.fetch_latest_version(timeout=7.5, url="https://example/x")
    assert got == "9.9.9"
    assert captured == {"url": "https://example/x", "timeout": 7.5}


def test_fetch_latest_version_default_url_is_pypi(monkeypatch):
    captured = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        return _fake_resp(b'{"info": {"version": "1.2.3"}}')

    monkeypatch.setattr(update.urllib.request, "urlopen", fake_urlopen)
    assert update.fetch_latest_version() == "1.2.3"
    assert captured["url"] == update.PYPI_URL


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.HTTPError(
            "u", 500, "err", Message(), None
        ),  # subclass of URLError
        urllib.error.URLError("down"),
        OSError("no network"),
        TimeoutError("timed out"),  # socket.timeout alias; subclass of OSError
    ],
)
def test_fetch_latest_version_network_errors_return_none(exc, monkeypatch):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(update.urllib.request, "urlopen", boom)
    assert update.fetch_latest_version(url="https://example/x") is None


def test_fetch_latest_version_malformed_json_returns_none(monkeypatch):
    monkeypatch.setattr(
        update.urllib.request, "urlopen", lambda *a, **k: _fake_resp(b"{not json")
    )
    assert update.fetch_latest_version(url="https://example/x") is None


def test_fetch_latest_version_missing_info_key_returns_none(monkeypatch):
    monkeypatch.setattr(
        update.urllib.request, "urlopen", lambda *a, **k: _fake_resp(b"{}")
    )
    assert update.fetch_latest_version(url="https://example/x") is None


def test_fetch_latest_version_missing_version_key_returns_none(monkeypatch):
    monkeypatch.setattr(
        update.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_resp(b'{"info": {}}'),
    )
    assert update.fetch_latest_version(url="https://example/x") is None


@pytest.mark.parametrize("bad_version", [1.5, 123, None, [1, 2, 3], {}])
def test_fetch_latest_version_rejects_non_string(bad_version, monkeypatch):
    """Bug 2 regression: a non-string PyPI version must yield None.

    Before the fix, ``return str(data["info"]["version"])`` coerced e.g. the
    JSON number ``1.5`` into the string ``"1.5"`` and fabricated a false
    "update available".
    """
    body = json.dumps({"info": {"version": bad_version}}).encode()
    monkeypatch.setattr(
        update.urllib.request, "urlopen", lambda *a, **k: _fake_resp(body)
    )
    assert update.fetch_latest_version(url="https://example/x") is None


# ---------------------------------------------------------------------------
# _read_cache — Bug 1 regression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("blob", "expected"),
    [
        ("[]", {}),
        ('"x"', {}),
        ("5", {}),
        ("true", {}),
        ("null", {}),
        ("3.14", {}),
        ('{"a": 1}', {"a": 1}),
        ("{}", {}),
        ("{not json", {}),
        ("", {}),
    ],
)
def test_read_cache_always_returns_dict(blob, expected, tmp_path: Path):
    """Bug 1 regression: _read_cache must always return a dict."""
    cache = tmp_path / "u.json"
    cache.write_text(blob)
    result = update._read_cache(cache)
    assert isinstance(result, dict)
    assert result == expected


def test_read_cache_missing_file_returns_empty_dict(tmp_path: Path):
    assert update._read_cache(tmp_path / "does-not-exist.json") == {}


# ---------------------------------------------------------------------------
# check_for_update — throttle, cache, defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blob", ["[]", '"x"', "5", "true", "null"])
def test_check_for_update_non_dict_cache_does_not_crash(
    blob, tmp_path: Path, monkeypatch
):
    """Bug 1 regression: valid-JSON-but-non-dict cache must not crash.

    Before the fix, ``cache.get(...)`` raised AttributeError on every CLI run
    whenever the cache file held e.g. ``[]`` or ``5``.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    cache.write_text(blob)
    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=lambda: "9.9.9"
    )
    assert got == "9.9.9"
    assert json.loads(cache.read_text()) == {"last_check": 1000.0, "latest": "9.9.9"}


def test_check_for_update_throttle_boundary_equal_refetches(
    tmp_path: Path, monkeypatch
):
    """now - last == interval MUST refetch (kills the >=  -> > mutation)."""
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    cache.write_text(json.dumps({"last_check": 1000.0, "latest": "1.0.0"}))
    calls = []

    def fetcher():
        calls.append(1)
        return "9.9.9"

    got = update.check_for_update(
        now=1100.0, cache_path=cache, interval=100, fetcher=fetcher
    )
    assert calls == [1]
    assert got == "9.9.9"
    assert json.loads(cache.read_text()) == {"last_check": 1100.0, "latest": "9.9.9"}


def test_check_for_update_just_below_boundary_serves_cache_without_fetch(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    cache.write_text(json.dumps({"last_check": 1000.0, "latest": "9.9.9"}))
    calls = []

    def fetcher():
        calls.append(1)
        return "5.5.5"

    got = update.check_for_update(
        now=1099.999, cache_path=cache, interval=100, fetcher=fetcher
    )
    assert calls == []
    assert got == "9.9.9"


def test_check_for_update_uses_cache_and_throttles(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
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


def test_check_for_update_failed_fetch_no_prior_cache(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=lambda: None
    )
    assert got is None
    assert json.loads(cache.read_text()) == {"last_check": 1000.0, "latest": None}


def test_check_for_update_failed_fetch_preserves_prior_latest(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    cache.write_text(json.dumps({"last_check": 0, "latest": "9.9.9"}))
    got = update.check_for_update(
        now=5000.0, cache_path=cache, interval=100, fetcher=lambda: None
    )
    assert got == "9.9.9"
    assert json.loads(cache.read_text()) == {"last_check": 5000.0, "latest": "9.9.9"}


def test_check_for_update_fetcher_returns_none_keeps_existing(tmp_path: Path):
    cache = tmp_path / "u.json"
    cache.write_text('{"last_check": 0, "latest": null}')
    got = update.check_for_update(
        now=1000.0,
        cache_path=cache,
        interval=100,
        fetcher=lambda: None,
    )
    assert got is None


def test_check_for_update_current_unparseable_returns_none(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "not-a-version")
    got = update.check_for_update(
        now=1.0,
        cache_path=tmp_path / "u.json",
        interval=0,
        fetcher=lambda: "9.9.9",
    )
    assert got is None


def test_check_for_update_default_now_uses_time_time(tmp_path: Path, monkeypatch):
    """now=None path: module time.time() is consulted."""
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    monkeypatch.setattr(update.time, "time", lambda: 4242.0)
    cache = tmp_path / "u.json"
    got = update.check_for_update(
        cache_path=cache, interval=100, fetcher=lambda: "9.9.9"
    )
    assert got == "9.9.9"
    assert json.loads(cache.read_text())["last_check"] == 4242.0


def test_check_for_update_default_cache_path_uses_module_lookup(
    tmp_path: Path, monkeypatch
):
    """cache_path=None path: globals()['cache_path']() is invoked."""
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    target = tmp_path / "nested" / "u.json"
    monkeypatch.setattr(update, "cache_path", lambda: target)
    got = update.check_for_update(now=1000.0, interval=100, fetcher=lambda: "9.9.9")
    assert got == "9.9.9"
    assert target.exists()
    assert json.loads(target.read_text())["latest"] == "9.9.9"


def test_check_for_update_throttles_after_failed_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    calls = []

    def failing_fetcher():
        calls.append(1)

    assert (
        update.check_for_update(
            now=1000.0, cache_path=cache, interval=100, fetcher=failing_fetcher
        )
        is None
    )
    assert len(calls) == 1
    assert (
        update.check_for_update(
            now=1050.0, cache_path=cache, interval=100, fetcher=failing_fetcher
        )
        is None
    )
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# _write_cache — OSError swallowed (removes pragma #2)
# ---------------------------------------------------------------------------


def test_write_cache_oserror_is_swallowed(tmp_path: Path, monkeypatch):
    def raise_oserror(*a, **k):
        raise OSError("read-only fs")

    monkeypatch.setattr(update.Path, "write_text", raise_oserror)
    # Must not raise.
    update._write_cache(tmp_path / "u.json", {"last_check": 1.0, "latest": "9.9.9"})


def test_check_for_update_correct_despite_write_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")

    def raise_oserror(*a, **k):
        raise OSError("read-only fs")

    monkeypatch.setattr(update.Path, "write_text", raise_oserror)
    got = update.check_for_update(
        now=1000.0,
        cache_path=tmp_path / "u.json",
        interval=100,
        fetcher=lambda: "9.9.9",
    )
    assert got == "9.9.9"


# ---------------------------------------------------------------------------
# current_version — distribution + fallback (removes pragma #1)
# ---------------------------------------------------------------------------


def test_current_version_from_distribution(monkeypatch):
    monkeypatch.setattr(update, "version", lambda pkg: "1.2.3")
    assert update.current_version() == "1.2.3"


def test_current_version_fallback_to_package_attribute(monkeypatch):
    def raise_not_found(pkg):
        raise PackageNotFoundError(pkg)

    monkeypatch.setattr(update, "version", raise_not_found)
    assert update.current_version() == henry_castillo.__version__


# ---------------------------------------------------------------------------
# perform_update — exact command vectors + rc handling (removes pragma #3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("present", "expected_cmd"),
    [
        ("uv", ["uv", "tool", "upgrade", "henry-castillo"]),
        ("pipx", ["pipx", "upgrade", "henry-castillo"]),
        (None, None),  # pip fallback, computed in-body
    ],
)
def test_perform_update_exact_command_vector(
    present, expected_cmd, monkeypatch, capsys
):
    if expected_cmd is None:
        expected_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "henry-castillo",
        ]

    def fake_which(name):
        return f"/usr/bin/{name}" if name == present else None

    captured = []
    monkeypatch.setattr(update.shutil, "which", fake_which)
    monkeypatch.setattr(
        update.subprocess, "call", lambda cmd: captured.append(cmd) or 0
    )
    rc = update.perform_update()
    assert rc == 0
    assert captured == [expected_cmd]
    out = capsys.readouterr().out
    assert out == f"Running: {' '.join(expected_cmd)}\n"


@pytest.mark.parametrize("rc", [0, 1, 2, 42, 130])
def test_perform_update_propagates_returncode(rc, monkeypatch):
    monkeypatch.setattr(
        update.shutil, "which", lambda n: "/usr/bin/uv" if n == "uv" else None
    )
    monkeypatch.setattr(update.subprocess, "call", lambda cmd: rc)
    assert update.perform_update() == rc


def test_perform_update_oserror_returns_one_and_prints(monkeypatch, capsys):
    monkeypatch.setattr(
        update.shutil, "which", lambda n: "/usr/bin/uv" if n == "uv" else None
    )

    def boom(cmd):
        raise OSError("exec format error")

    monkeypatch.setattr(update.subprocess, "call", boom)
    rc = update.perform_update()
    assert rc == 1
    out = capsys.readouterr().out
    assert "Running: uv tool upgrade henry-castillo\n" in out
    assert "Update failed: exec format error\n" in out


# ---------------------------------------------------------------------------
# update_notice — exact full string
# ---------------------------------------------------------------------------


def test_update_notice_exact_string(monkeypatch):
    monkeypatch.setattr(update, "current_version", lambda: "0.1.0")
    assert update.update_notice("9.9.9") == (
        "A new release of henry-castillo is available: 0.1.0 -> 9.9.9. "
        "Run `henry-castillo --update` to upgrade."
    )


# ---------------------------------------------------------------------------
# cache_path — XDG handling incl. the relative-path hardening
# ---------------------------------------------------------------------------


def test_cache_path_unset_uses_home_cache(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(update.Path, "home", classmethod(lambda cls: Path("/home/u")))
    assert update.cache_path() == Path(
        "/home/u/.cache/henry-castillo/update-check.json"
    )


def test_cache_path_empty_xdg_falls_back(monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", "")
    monkeypatch.setattr(update.Path, "home", classmethod(lambda cls: Path("/home/u")))
    assert update.cache_path() == Path(
        "/home/u/.cache/henry-castillo/update-check.json"
    )


def test_cache_path_relative_xdg_falls_back(monkeypatch):
    """XDG hardening: per the XDG spec a non-absolute path must be ignored."""
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/dir")
    monkeypatch.setattr(update.Path, "home", classmethod(lambda cls: Path("/home/u")))
    assert update.cache_path() == Path(
        "/home/u/.cache/henry-castillo/update-check.json"
    )


def test_cache_path_absolute_xdg_used_verbatim(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = update.cache_path()
    assert p == tmp_path / "henry-castillo" / "update-check.json"
