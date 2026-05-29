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
from henry_castillo.__main__ import main as _main

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

        def read(self, *_a):
            # Accept (and ignore) an optional size arg: production now calls
            # ``resp.read(_MAX_PYPI_BYTES + 1)`` to cap the buffered body.
            # Returning the (small) test body verbatim is correct -- the cap
            # only rejects bodies strictly larger than the limit.
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


@pytest.mark.parametrize(
    "body",
    [
        b"[]",
        b'"x"',
        b"5",
        b"null",
        b"3.14",
        b"[1,2,3]",
    ],
)
def test_fetch_latest_version_non_dict_body_returns_none(body, monkeypatch):
    """CLI-crash regression: a valid-JSON-but-non-**top-level**-dict PyPI body
    must yield None, not raise.

    This covers the *top-level* ``data`` guard only (the whole body is a JSON
    array/string/number/bool/null). Before the top-level
    ``isinstance(data, dict)`` guard, ``data["info"]`` was indexed
    unconditionally and a non-dict top-level body raised an uncaught
    ``TypeError`` that propagated out of ``fetch_latest_version`` (the
    ``except`` tuple did not catch ``TypeError``), crashing the CLI's
    background update check. The *nested* case (``data`` is a dict but
    ``data["info"]`` is not) is covered separately by
    ``test_fetch_latest_version_info_not_dict_returns_none``.
    """
    monkeypatch.setattr(
        update.urllib.request, "urlopen", lambda *a, **k: _fake_resp(body)
    )
    assert update.fetch_latest_version(url="https://x") is None


@pytest.mark.parametrize("x", [None, 0, 1.5, True, "s", [1, 2, 3]])
def test_fetch_latest_version_info_not_dict_returns_none(x, monkeypatch):
    """FIX 1 regression: ``{"info": <non-dict>}`` must yield None, not raise.

    The earlier fix only guarded the *top-level* ``data``. A body whose
    ``info`` value is not a dict (``null``/number/bool/string/array) still
    reached ``data["info"]["version"]``, which raises a ``TypeError`` for
    ``None``/``int``/``float``/``bool``/``str`` (or worse, silently indexes a
    list). ``TypeError`` is NOT in the ``except (OSError, ValueError,
    KeyError)`` tuple, so it propagated through ``check_for_update`` and
    crashed the CLI on every interactive run / ``--check-update``.
    """
    body = json.dumps({"info": x}).encode()
    monkeypatch.setattr(
        update.urllib.request, "urlopen", lambda *a, **k: _fake_resp(body)
    )
    assert update.fetch_latest_version(url="https://x") is None


def test_check_for_update_info_null_body_does_not_raise(tmp_path: Path, monkeypatch):
    """End-to-end FIX 1: the DEFAULT fetcher path with a ``{"info": null}``
    body must return None, NOT raise.

    Drives the real ``fetch_latest_version`` (default fetcher, not stubbed)
    via a fake ``urlopen`` so a regression of the nested-``info`` guard
    surfaces here as an uncaught ``TypeError`` out of ``check_for_update``.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    monkeypatch.setattr(
        update.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_resp(b'{"info": null}'),
    )
    got = update.check_for_update(
        now=1000.0, cache_path=tmp_path / "u.json", interval=100
    )
    assert got is None


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


def test_fetch_latest_version_oversize_body_returns_none(monkeypatch):
    """FIX 5 regression: a body larger than ``_MAX_PYPI_BYTES`` must yield
    None WITHOUT buffering/parsing it (memory-DoS guard).

    The fake ``resp.read(n)`` honors the requested size and returns one byte
    past the cap, exactly as a real socket read of an over-large stream
    would, so the length check trips and we never hand >2MiB to
    ``json.loads``.
    """
    over = update._MAX_PYPI_BYTES

    class _Big:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=None):
            # Real urllib resp.read(n) returns at most n bytes. We return
            # exactly n (= cap + 1) bytes of valid-prefix JSON so the only
            # thing that can reject it is the size cap, not a parse error.
            assert n == over + 1
            return b'{"info": {"version": "9.9.9"}}' + b" " * (over + 1)

    monkeypatch.setattr(update.urllib.request, "urlopen", lambda *a, **k: _Big())
    assert update.fetch_latest_version(url="https://x") is None


def test_fetch_latest_version_body_exactly_at_cap_still_parses(monkeypatch):
    """A body whose length is exactly ``_MAX_PYPI_BYTES`` is still parsed
    (the cap rejects only strictly-larger bodies)."""
    payload = json.dumps({"info": {"version": "1.2.3"}}).encode()
    pad = update._MAX_PYPI_BYTES - len(payload)
    # Valid JSON padded with leading whitespace to land exactly on the cap.
    body = b" " * pad + payload
    assert len(body) == update._MAX_PYPI_BYTES
    monkeypatch.setattr(
        update.urllib.request, "urlopen", lambda *a, **k: _fake_resp(body)
    )
    assert update.fetch_latest_version(url="https://x") == "1.2.3"


def test_fetch_latest_version_small_body_still_returns_version(monkeypatch):
    """FIX 5 must not regress the happy path: a normal small body still
    yields the version (the read-with-size arg returns the full small body)."""
    monkeypatch.setattr(
        update.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_resp(b'{"info": {"version": "4.5.6"}}'),
    )
    assert update.fetch_latest_version(url="https://x") == "4.5.6"


def test_max_pypi_bytes_is_two_mib():
    """Pin the cap constant so a mutation away from 2 MiB is caught."""
    assert update._MAX_PYPI_BYTES == 2 * 1024 * 1024


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


def test_check_for_update_default_interval_is_one_day():
    """The throttle window constant is exactly 86400s (1 day).

    Kills a mutation of ``CHECK_INTERVAL_SECONDS`` away from one day.
    """
    assert update.CHECK_INTERVAL_SECONDS == 86400


def test_check_for_update_default_interval_throttles_at_one_day(
    tmp_path: Path, monkeypatch
):
    """Behavioral pin of the DEFAULT interval (no ``interval=`` passed).

    ~12h after ``last_check`` must NOT refetch (still inside the 1-day
    window); ~25h after must refetch. This kills any mutation of
    ``CHECK_INTERVAL_SECONDS`` (the default arg value), which a test that
    always passes an explicit ``interval=`` cannot catch.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    last = 1_000_000.0
    cache.write_text(json.dumps({"last_check": last, "latest": "1.0.0"}))
    calls = []

    def fetcher():
        calls.append(1)
        return "9.9.9"

    # ~12h later: inside the default 86400s window -> served from cache.
    got = update.check_for_update(
        now=last + 12 * 3600, cache_path=cache, fetcher=fetcher
    )
    assert calls == []
    assert got == "1.0.0"

    # ~25h later: past the default 86400s window -> refetch.
    got = update.check_for_update(
        now=last + 25 * 3600, cache_path=cache, fetcher=fetcher
    )
    assert calls == [1]
    assert got == "9.9.9"


def test_check_for_update_creates_multi_level_cache_dirs(tmp_path: Path, monkeypatch):
    """The cache parent is created with ALL missing intermediate levels.

    Pointing the cache at a path with >=2 missing parent components proves
    ``mkdir(parents=True)`` -- a ``parents=False`` mutation would raise
    ``FileNotFoundError`` (swallowed by ``_write_cache``) so the file would
    NOT be written and these assertions would fail.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "a" / "b" / "c" / "u.json"
    assert not cache.parent.exists()
    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=lambda: "9.9.9"
    )
    assert got == "9.9.9"
    assert cache.is_file()
    assert json.loads(cache.read_text()) == {
        "last_check": 1000.0,
        "latest": "9.9.9",
    }


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
# update_notice — exact full string (the emitted version is PEP 440 NORMALIZED)
# ---------------------------------------------------------------------------


def test_update_notice_exact_string(monkeypatch):
    """Exact contract: the message embeds the PEP 440 *normalized* version.

    ``"9.9.9"`` is already normalized, so the string is unchanged; this
    pins the exact format. The normalization itself (stripping trailing
    control/whitespace bytes) is asserted by the parametrized test below.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.1.0")
    assert update.update_notice("9.9.9") == (
        "A new release of henry-castillo is available: 0.1.0 -> 9.9.9. "
        "Run `henry-castillo --update` to upgrade."
    )


@pytest.mark.parametrize(
    ("hostile", "normalized"),
    [
        ("999.0.0\r", "999.0.0"),
        ("1.0.0\x0c", "1.0.0"),
        ("2.3.4\n", "2.3.4"),
        ("5.6.7\x0b", "5.6.7"),
        ("  8.9.10\t", "8.9.10"),
        # packaging normalizes case/format too: this proves it is the
        # *normalized* str(Version(...)), not a mere whitespace strip.
        ("1.0.0RC1\r\n", "1.0.0rc1"),
    ],
)
def test_update_notice_normalizes_hostile_version(hostile, normalized, monkeypatch):
    """FIX 4 regression: a poisoned ``latest`` with trailing control/whitespace
    bytes must NOT garble the terminal line.

    ``packaging.Version`` tolerates trailing ``\\r``/``\\n``/``\\x0c``/
    ``\\x0b``/whitespace, so the raw string would emit those control bytes
    into the user's TTY. The notice must instead contain the PEP 440
    *normalized* form and no character from ``str.isspace`` / the C0
    control range.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.1.0")
    msg = update.update_notice(hostile)
    expected = (
        f"A new release of henry-castillo is available: 0.1.0 -> {normalized}. "
        f"Run `henry-castillo --update` to upgrade."
    )
    assert msg == expected
    # No control / whitespace-class byte anywhere in the rendered notice
    # except the single ASCII spaces that are part of the literal template.
    assert "\r" not in msg
    assert "\n" not in msg
    assert "\x0c" not in msg
    assert "\x0b" not in msg
    assert "\t" not in msg
    assert not any(ord(c) < 0x20 for c in msg)


def test_update_notice_unparseable_version_falls_back_to_stripped(monkeypatch):
    """Defensive fallback: if ``Version()`` somehow cannot parse ``latest``
    (``check_for_update`` should never return such a value, but be safe), the
    notice still emits a whitespace-stripped form -- never raw control bytes.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.1.0")
    msg = update.update_notice("not a version\r\n")
    assert "\r" not in msg
    assert "\n" not in msg
    assert "notaversion" in msg


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


# ---------------------------------------------------------------------------
# NEW: corrupt-cache hardening — BUG 1 (non-numeric last_check) and
# BUG 2 (non-string cached latest). Tests written FIRST (TDD); they must
# fail before the fixes are applied and pass after.
# ---------------------------------------------------------------------------


def test_check_for_update_string_last_check_does_not_raise(tmp_path: Path, monkeypatch):
    """BUG 1 regression: last_check='xxx' must not crash with TypeError.

    Before the fix, ``now - last`` where last is a str raises
    ``TypeError: unsupported operand type(s) for -: 'float' and 'str'``.
    After the fix the bad value is coerced to 0 (stale) -> fetcher runs.
    """
    monkeypatch.setattr(update, "current_version", lambda: "9.9.9")
    cache = tmp_path / "u.json"
    cache.write_text('{"last_check": "xxx", "latest": "9.9.9"}')
    # Must return None (not raise), even if fetcher finds nothing new.
    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=lambda: None
    )
    assert got is None


@pytest.mark.parametrize(
    "bad_last",
    [
        None,  # JSON null -> not int/float -> coerce to 0
        [1],  # list -> coerce to 0
        True,  # bool subclass of int, but excluded -> coerce to 0
    ],
)
def test_check_for_update_non_numeric_last_check_types_do_not_raise(
    bad_last, tmp_path: Path, monkeypatch
):
    """BUG 1 regression (parametrized): null, list, and bool last_check must not crash.

    True is an int subclass so ``isinstance(True, (int, float))`` would be True
    without the bool exclusion — the fix must explicitly reject bool.
    """
    monkeypatch.setattr(update, "current_version", lambda: "9.9.9")
    cache = tmp_path / "u.json"
    cache.write_text(json.dumps({"last_check": bad_last, "latest": "1.0.0"}))
    # Must not raise; coerced last == 0 -> stale -> fetcher runs.
    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=lambda: None
    )
    assert got is None  # current == "9.9.9", fetcher returns None, so None


def test_check_for_update_throttled_non_string_latest_does_not_raise(
    tmp_path: Path, monkeypatch
):
    """BUG 2 regression: a throttled cache with latest=123 (int) must not crash.

    Before the fix, ``is_outdated(current, 123)`` raises TypeError because
    ``Version(123)`` (packaging) raises TypeError, not InvalidVersion, and the
    except only caught InvalidVersion.  After the fix the non-string latest is
    coerced to None in check_for_update, so is_outdated is never called with it.
    """
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    now = 1_000_000.0
    cache = tmp_path / "u.json"
    # Throttled: last_check == now so now - last == 0 < interval → skip fetch.
    cache.write_text('{"last_check": 1000000.0, "latest": 123}')
    got = update.check_for_update(
        now=now, cache_path=cache, interval=100, fetcher=lambda: None
    )
    assert got is None


@pytest.mark.parametrize("bad_latest", [[1], True])
def test_check_for_update_throttled_list_and_bool_latest_do_not_raise(
    bad_latest, tmp_path: Path, monkeypatch
):
    """BUG 2 regression (parametrized): throttled list/bool latest must not crash."""
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    now = 1_000_000.0
    cache = tmp_path / "u.json"
    cache.write_text(json.dumps({"last_check": now, "latest": bad_latest}))
    got = update.check_for_update(
        now=now, cache_path=cache, interval=100, fetcher=lambda: None
    )
    assert got is None


def test_is_outdated_non_string_latest_int_returns_false():
    """Defense-in-depth: is_outdated with int latest must return False, not crash."""
    assert update.is_outdated("0.0.0", 123) is False  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]


def test_is_outdated_non_string_latest_list_returns_false():
    """Defense-in-depth: is_outdated with list latest must return False, not crash."""
    assert update.is_outdated("0.0.0", ["x"]) is False  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]


# Happy-path regression: well-typed caches must still work exactly as before.


def test_check_for_update_valid_cache_still_throttles_and_returns_latest(
    tmp_path: Path, monkeypatch
):
    """Well-typed throttled cache: coercion must not disturb the happy path."""
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    now = 1_000_000.0
    cache = tmp_path / "u.json"
    cache.write_text('{"last_check": 1000000.0, "latest": "9.9.9"}')
    calls: list[int] = []
    got = update.check_for_update(
        now=now,
        cache_path=cache,
        interval=100,
        fetcher=lambda: calls.append(1) or "5.5.5",
    )
    # Throttled → no fetch, still returns cached latest.
    assert calls == []
    assert got == "9.9.9"


def test_check_for_update_valid_stale_cache_still_fetches(tmp_path: Path, monkeypatch):
    """Well-typed stale cache: fetch is triggered and result returned."""
    monkeypatch.setattr(update, "current_version", lambda: "0.0.0")
    cache = tmp_path / "u.json"
    cache.write_text('{"last_check": 0.0, "latest": "1.0.0"}')
    calls: list[int] = []

    def fetcher():
        calls.append(1)
        return "9.9.9"

    got = update.check_for_update(
        now=1000.0, cache_path=cache, interval=100, fetcher=fetcher
    )
    assert calls == [1]
    assert got == "9.9.9"


# End-to-end: tampered on-disk cache must not crash main(["--check-update"]).


def test_main_check_update_with_tampered_cache_returns_zero(
    tmp_path: Path, monkeypatch
):
    """End-to-end BUG 1 + BUG 2: main(["--check-update"]) with a tampered cache.

    Sets XDG_CACHE_HOME to tmp_path, writes a corrupt cache
    ``{"last_check":"xxx","latest":"9.9.9"}`` (triggers BUG 1), and asserts
    that main returns 0 and does NOT raise.
    """
    cache_dir = tmp_path / "henry-castillo"
    cache_dir.mkdir(parents=True)
    (cache_dir / "update-check.json").write_text(
        json.dumps({"last_check": "xxx", "latest": "9.9.9"})
    )
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    # Stub the fetcher so no real network call is made.
    monkeypatch.setattr(update, "fetch_latest_version", lambda **k: None)
    rc = _main(["--check-update"])
    assert rc == 0
