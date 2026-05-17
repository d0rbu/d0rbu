"""Deterministic tests for the rolling minimum-dependency-age guard.

The guard lives OUTSIDE the ``henry_castillo`` package
(``scripts/check_min_dependency_age.py``) on purpose, so it is not measured
by the ``--cov=henry_castillo --cov-fail-under=100`` gate. These tests are
still collected by pytest.

No real network is ever used: ``now`` is injected and the npm registry
lookup is replaced with a fake. The autouse network-blocking fixture in
``tests/conftest.py`` also applies, so a regression that performs a real
request fails loudly rather than flaking.
"""

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the single-file script by path (it is intentionally not a package
# module so it stays out of the henry_castillo coverage gate).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check_min_dependency_age.py"
_spec = importlib.util.spec_from_file_location("check_min_dependency_age", _SCRIPT)
assert _spec is not None and _spec.loader is not None
guard = importlib.util.module_from_spec(_spec)
# Register before executing so dataclasses' type introspection can resolve
# the module via sys.modules (string annotations + from __future__).
sys.modules["check_min_dependency_age"] = guard
_spec.loader.exec_module(guard)


UTC = timezone.utc


def _dt(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


# ---------------------------------------------------------------------------
# parse_uv_lock
# ---------------------------------------------------------------------------

# All timestamps are intentionally ancient so "clean" main() cases are
# deterministically clean regardless of the day the suite runs.
UV_LOCK_SAMPLE = """\
version = 1
revision = 3
requires-python = ">=3.10"

[[package]]
name = "annotated-doc"
version = "0.0.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://e/a.tgz", upload-time = "2020-11-10T22:07:42.062Z" }
wheels = [
    { url = "https://e/a.whl", upload-time = "2020-11-10T22:07:40.673Z" },
]

[[package]]
name = "henry-castillo"
source = { editable = "." }
dependencies = [
    { name = "packaging" },
    { name = "rich" },
]

[[package]]
version = "8.4.0"
source = { registry = "https://pypi.org/simple" }
name = "click"
wheels = [
    { url = "https://e/c.whl", upload-time = "2021-05-17T00:47:56.842Z" },
]
"""


def test_parse_uv_lock_extracts_name_version_upload_time():
    pkgs = guard.parse_uv_lock(UV_LOCK_SAMPLE)
    by_name = {p[0]: p for p in pkgs}

    # registry package with sdist upload-time
    assert by_name["annotated-doc"] == (
        "annotated-doc",
        "0.0.4",
        _dt(2020, 11, 10, 22, 7, 42, 62000),
    )


def test_parse_uv_lock_tolerates_key_ordering_and_wheel_only():
    """`click` has version before name and only a wheels upload-time."""
    pkgs = guard.parse_uv_lock(UV_LOCK_SAMPLE)
    by_name = {p[0]: p for p in pkgs}
    assert by_name["click"] == (
        "click",
        "8.4.0",
        _dt(2021, 5, 17, 0, 47, 56, 842000),
    )


def test_parse_uv_lock_root_editable_has_no_upload_time():
    """The root/editable project (no upload-time) yields None for time."""
    pkgs = guard.parse_uv_lock(UV_LOCK_SAMPLE)
    by_name = {p[0]: p for p in pkgs}
    assert "henry-castillo" in by_name
    assert by_name["henry-castillo"][2] is None


def test_parse_uv_lock_empty_text_returns_empty_list():
    assert guard.parse_uv_lock("") == []


# ---------------------------------------------------------------------------
# parse_npm_lock
# ---------------------------------------------------------------------------

NPM_LOCK_SAMPLE = {
    "name": "henry-castillo",
    "version": "0.0.0",
    "lockfileVersion": 3,
    "packages": {
        "": {
            "name": "henry-castillo",
            "version": "0.0.0",
            "devDependencies": {"typescript": "5.7.2"},
        },
        "node_modules/typescript": {
            "version": "5.7.2",
            "resolved": "https://registry.npmjs.org/typescript/-/typescript-5.7.2.tgz",
            "integrity": "sha512-xxx",
            "dev": True,
        },
        "node_modules/@types/node": {
            "version": "25.8.0",
            "resolved": "https://registry.npmjs.org/@types/node/-/node-25.8.0.tgz",
            "integrity": "sha512-yyy",
            "dev": True,
        },
        "node_modules/local-link": {
            "resolved": "link:../somewhere",
            "link": True,
        },
        "node_modules/file-dep": {
            "version": "1.0.0",
            "resolved": "file:../tarballs/file-dep-1.0.0.tgz",
        },
        "node_modules/no-resolved": {
            "version": "9.9.9",
        },
    },
}


def test_parse_npm_lock_returns_only_registry_deps():
    pkgs = guard.parse_npm_lock(NPM_LOCK_SAMPLE)
    assert sorted(pkgs) == sorted(
        [
            ("typescript", "5.7.2"),
            ("@types/node", "25.8.0"),
        ]
    )


def test_parse_npm_lock_missing_packages_key_returns_empty():
    assert guard.parse_npm_lock({}) == []


# ---------------------------------------------------------------------------
# iso_to_dt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "2025-11-10T22:07:42.062Z",
        "2025-11-10T22:07:42.062+00:00",
    ],
)
def test_iso_to_dt_z_and_offset_are_equal_utc(text):
    got = guard.iso_to_dt(text)
    assert got == _dt(2025, 11, 10, 22, 7, 42, 62000)
    assert got.tzinfo is not None
    assert got.utcoffset() == timedelta(0)


def test_iso_to_dt_z_equals_explicit_offset():
    assert guard.iso_to_dt("2026-01-02T03:04:05Z") == guard.iso_to_dt(
        "2026-01-02T03:04:05+00:00"
    )


# ---------------------------------------------------------------------------
# find_violations — uv side
# ---------------------------------------------------------------------------

NOW = _dt(2026, 5, 17, 12, 0, 0)
MIN_AGE = timedelta(days=7)


def _no_npm(name, version):  # pragma: no cover - injected, never called here
    raise AssertionError("npm lookup must not be called for uv-only cases")


@pytest.mark.parametrize(
    ("uploaded", "expect_violation"),
    [
        (NOW - timedelta(days=2), True),  # 2 days old -> too fresh
        (NOW - timedelta(days=30), False),  # 30 days old -> fine
    ],
)
def test_find_violations_uv_age(uploaded, expect_violation):
    uv_pkgs = [("freshpkg", "1.0.0", uploaded)]
    violations, warnings = guard.find_violations(
        uv_pkgs,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
    )
    assert warnings == []
    assert (len(violations) == 1) is expect_violation
    if expect_violation:
        v = violations[0]
        assert v.ecosystem == "uv"
        assert v.name == "freshpkg"
        assert v.version == "1.0.0"


def test_find_violations_uv_no_upload_time_is_ignored():
    """Root/path dep without an upload-time is never a violation."""
    violations, warnings = guard.find_violations(
        [("henry-castillo", "0.0.0", None)],
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
    )
    assert violations == []
    assert warnings == []


@pytest.mark.parametrize(
    ("delta", "expect_violation"),
    [
        # Pin the boundary exactly like the update-throttle test:
        # age == min_age  -> NOT a violation (>= min_age is OK)
        # age just below  -> violation (< min_age)
        (timedelta(days=7), False),
        (timedelta(days=7) - timedelta(seconds=1), True),
        (timedelta(days=7) + timedelta(seconds=1), False),
    ],
)
def test_find_violations_uv_boundary_is_pinned(delta, expect_violation):
    uv_pkgs = [("boundary", "2.0.0", NOW - delta)]
    violations, _ = guard.find_violations(
        uv_pkgs,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
    )
    assert (len(violations) == 1) is expect_violation


# ---------------------------------------------------------------------------
# find_violations — npm side
# ---------------------------------------------------------------------------


def test_find_violations_npm_fresh_is_violation():
    def fetch(name, version):
        assert (name, version) == ("freshnpm", "1.2.3")
        return NOW - timedelta(days=1)

    violations, warnings = guard.find_violations(
        [],
        [("freshnpm", "1.2.3")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=fetch,
    )
    assert warnings == []
    assert len(violations) == 1
    assert violations[0].ecosystem == "npm"
    assert violations[0].name == "freshnpm"


def test_find_violations_npm_old_is_clean():
    violations, warnings = guard.find_violations(
        [],
        [("oldnpm", "9.9.9")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=lambda n, v: NOW - timedelta(days=60),
    )
    assert violations == []
    assert warnings == []


def test_find_violations_npm_lookup_failure_is_warning_not_violation():
    """Fail-open for transient registry errors: a None lookup is a WARNING."""
    violations, warnings = guard.find_violations(
        [],
        [("mystery", "0.1.0")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=lambda n, v: None,
    )
    assert violations == []
    assert len(warnings) == 1
    assert "mystery" in warnings[0]
    assert "0.1.0" in warnings[0]


@pytest.mark.parametrize(
    ("delta", "expect_violation"),
    [
        (timedelta(days=7), False),
        (timedelta(days=7) - timedelta(seconds=1), True),
        (timedelta(days=7) + timedelta(seconds=1), False),
    ],
)
def test_find_violations_npm_boundary_is_pinned(delta, expect_violation):
    violations, warnings = guard.find_violations(
        [],
        [("npmboundary", "3.0.0")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=lambda n, v: NOW - delta,
    )
    assert warnings == []
    assert (len(violations) == 1) is expect_violation


# ---------------------------------------------------------------------------
# npm_published_at
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def test_npm_published_at_parses_time_for_version():
    captured = {}

    def opener(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        body = json.dumps(
            {
                "name": "leftpad",
                "time": {
                    "created": "2020-01-01T00:00:00.000Z",
                    "1.0.0": "2024-01-02T03:04:05.000Z",
                    "1.1.0": "2025-06-07T08:09:10.000Z",
                },
            }
        ).encode()
        return _FakeResp(body)

    got = guard.npm_published_at("leftpad", "1.1.0", opener=opener, timeout=5)
    assert got == _dt(2025, 6, 7, 8, 9, 10)
    assert captured["url"] == "https://registry.npmjs.org/leftpad"
    assert captured["timeout"] == 5


def test_npm_published_at_url_encodes_scoped_name():
    captured = {}

    def opener(url, timeout=None):
        captured["url"] = url
        body = json.dumps({"time": {"25.8.0": "2025-01-01T00:00:00Z"}}).encode()
        return _FakeResp(body)

    guard.npm_published_at("@types/node", "25.8.0", opener=opener)
    # The scope slash must be encoded so the path stays a single segment.
    assert captured["url"] == "https://registry.npmjs.org/@types%2Fnode"


def test_npm_published_at_opener_oserror_returns_none():
    def opener(url, timeout=None):
        raise OSError("connection refused")

    assert guard.npm_published_at("x", "1.0.0", opener=opener) is None


def test_npm_published_at_bad_json_returns_none():
    def opener(url, timeout=None):
        return _FakeResp(b"{not json")

    assert guard.npm_published_at("x", "1.0.0", opener=opener) is None


def test_npm_published_at_version_absent_returns_none():
    body = json.dumps({"time": {"2.0.0": "2025-01-01T00:00:00Z"}}).encode()

    def opener(url, timeout=None):
        return _FakeResp(body)

    assert guard.npm_published_at("x", "1.0.0", opener=opener) is None


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _write_locks(tmp_path: Path, uv_text: str, npm_obj: dict) -> tuple[Path, Path]:
    uv_lock = tmp_path / "uv.lock"
    npm_lock = tmp_path / "package-lock.json"
    uv_lock.write_text(uv_text)
    npm_lock.write_text(json.dumps(npm_obj))
    return uv_lock, npm_lock


_FRESH_UV = """\
[[package]]
name = "veryfresh"
version = "9.9.9"
source = {{ registry = "https://pypi.org/simple" }}
sdist = {{ url = "https://e/v.tgz", upload-time = "{ts}" }}
"""


def test_main_clean_returns_zero(tmp_path, capsys):
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    # Patch the npm fetcher so it never hits the network and reports old pkgs.
    rc = guard.main(
        [
            "--uv-lock",
            str(uv_lock),
            "--npm-lock",
            str(npm_lock),
            "--skip-npm",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK" in out or "no violations" in out.lower()


def test_main_uv_violation_returns_one_and_reports(tmp_path, capsys):
    fresh = datetime.now(UTC) - timedelta(hours=12)
    ts = fresh.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "veryfresh==9.9.9" in out
    assert "< 7d" in out


def test_main_skip_npm_ignores_npm_entirely(tmp_path, monkeypatch, capsys):
    # An npm package that WOULD be a violation if checked.
    def boom(*a, **k):  # pragma: no cover - must never run under --skip-npm
        raise AssertionError("npm registry must not be queried with --skip-npm")

    monkeypatch.setattr(guard, "npm_published_at", boom)
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    assert rc == 0
    capsys.readouterr()


def test_main_npm_violation_via_injected_fetcher(tmp_path, monkeypatch, capsys):
    fresh = datetime.now(UTC) - timedelta(days=1)
    monkeypatch.setattr(guard, "npm_published_at", lambda n, v, **k: fresh)
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    rc = guard.main(["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "typescript==5.7.2" in out


def test_main_npm_registry_error_is_warning_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(guard, "npm_published_at", lambda n, v, **k: None)
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    rc = guard.main(["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "warning" in out.lower()
    assert "typescript" in out


def test_main_missing_lock_files_returns_zero(tmp_path, capsys):
    rc = guard.main(
        [
            "--uv-lock",
            str(tmp_path / "absent-uv.lock"),
            "--npm-lock",
            str(tmp_path / "absent-package-lock.json"),
            "--skip-npm",
        ]
    )
    assert rc == 0
    capsys.readouterr()


def test_main_min_age_days_is_honored(tmp_path, capsys):
    # Package uploaded 10 days ago: fine at default 7, a violation at 14.
    ten_days = datetime.now(UTC) - timedelta(days=10)
    ts = ten_days.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)

    rc_default = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    capsys.readouterr()
    assert rc_default == 0

    rc_strict = guard.main(
        [
            "--uv-lock",
            str(uv_lock),
            "--npm-lock",
            str(npm_lock),
            "--skip-npm",
            "--min-age-days",
            "14",
        ]
    )
    out = capsys.readouterr().out
    assert rc_strict == 1
    assert "veryfresh==9.9.9" in out
    assert "< 14d" in out


def test_main_report_text_is_exact_for_uv_violation(tmp_path, capsys):
    uploaded = datetime.now(UTC) - timedelta(hours=24)
    ts = uploaded.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 1
    # iso_to_dt drops the zero microseconds, so the rendered timestamp has
    # no fractional part. e.g.:
    #   [uv] veryfresh==9.9.9 published 2026-05-16T12:00:00+00:00 (24h old, < 7d)
    iso = ts.replace(".000Z", "+00:00")
    expected_line = f"[uv] veryfresh==9.9.9 published {iso} (24h old, < 7d)"
    assert expected_line in out
    # And it appears exactly as one indented report line.
    assert f"  {expected_line}\n" in out
