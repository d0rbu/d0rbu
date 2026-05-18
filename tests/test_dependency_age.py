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
import subprocess
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

    # registry package with sdist upload-time -> 4-tuple incl. source kind.
    assert by_name["annotated-doc"] == (
        "annotated-doc",
        "0.0.4",
        _dt(2020, 11, 10, 22, 7, 42, 62000),
        "registry",
    )


def test_parse_uv_lock_tolerates_key_ordering_and_wheel_only():
    """`click` has version before name and only a wheels upload-time."""
    pkgs = guard.parse_uv_lock(UV_LOCK_SAMPLE)
    by_name = {p[0]: p for p in pkgs}
    assert by_name["click"] == (
        "click",
        "8.4.0",
        _dt(2021, 5, 17, 0, 47, 56, 842000),
        "registry",
    )


def test_parse_uv_lock_root_editable_has_no_upload_time():
    """The root/editable project (no upload-time) yields None for time and
    an ``editable`` source kind (NOT a registry package)."""
    pkgs = guard.parse_uv_lock(UV_LOCK_SAMPLE)
    by_name = {p[0]: p for p in pkgs}
    assert "henry-castillo" in by_name
    assert by_name["henry-castillo"][2] is None
    assert by_name["henry-castillo"][3] == "editable"


def test_parse_uv_lock_empty_text_returns_empty_list():
    assert guard.parse_uv_lock("") == []


@pytest.mark.parametrize(
    "sep",
    [
        "\x0b",  # VT
        "\x0c",  # FF
        "\x1c",  # FS
        "\x1d",  # GS
        "\x1e",  # RS
        "\x85",  # NEL
        "\u2028",  # LINE SEPARATOR
        "\u2029",  # PARAGRAPH SEPARATOR
    ],
)
def test_parse_uv_lock_unicode_line_sep_does_not_fracture_value(sep):
    """FIX 6 regression: a Unicode line separator embedded in a quoted value
    must NOT fracture the ``key = "..."`` line.

    ``str.splitlines()`` splits on ``\\x0b\\x0c\\x1c\\x1d\\x1e\\x85\\u2028
    \\u2029`` (and more) -- but TOML newlines are ONLY ``\\n``/``\\r\\n``. A
    crafted ``version`` value containing such a code point would, under
    ``splitlines()``, break the quoted string across two pseudo-lines so
    ``_scalar`` sees an unterminated quote -> the package is dropped or its
    version truncated (which, post-FIX-2, could let a tampered fresh pin slip
    past the age check by mis-identifying its version). With
    ``replace("\\r\\n","\\n").split("\\n")`` the value stays intact.
    """
    version_value = f"1.{sep}0.0"
    block = (
        "version = 1\n"
        "\n"
        "[[package]]\n"
        'name = "evil"\n'
        f'version = "{version_value}"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'sdist = { url = "https://e/e.tgz", '
        'upload-time = "2020-01-01T00:00:00Z" }\n'
    )
    pkgs = guard.parse_uv_lock(block)
    by_name = {p[0]: p for p in pkgs}
    assert "evil" in by_name, f"package dropped when value held {sep!r}"
    _name, version, upload, source_kind = by_name["evil"]
    assert version == version_value, (
        f"version truncated/fractured by {sep!r}: got {version!r}"
    )
    assert upload == _dt(2020, 1, 1, 0, 0, 0)
    assert source_kind == "registry"


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
    },
}


def _npm_names_kinds(pkgs):
    """Reduce parse_npm_lock 4-tuples to ``{name: kind}`` for assertions."""
    return {name: kind for name, _v, _r, kind in pkgs}


def test_parse_npm_lock_returns_only_registry_deps():
    """Genuine registry deps come back tagged ``registry`` with their
    ``resolved``; ``link:`` and ``file:`` entries are excluded entirely."""
    pkgs = guard.parse_npm_lock(NPM_LOCK_SAMPLE)
    by_name = {name: (name, v, r, kind) for name, v, r, kind in pkgs}
    assert set(by_name) == {"typescript", "@types/node"}
    assert by_name["typescript"] == (
        "typescript",
        "5.7.2",
        "https://registry.npmjs.org/typescript/-/typescript-5.7.2.tgz",
        "registry",
    )
    assert by_name["@types/node"] == (
        "@types/node",
        "25.8.0",
        "https://registry.npmjs.org/@types/node/-/node-25.8.0.tgz",
        "registry",
    )


def test_parse_npm_lock_missing_packages_key_returns_empty():
    assert guard.parse_npm_lock({}) == []


# ---------------------------------------------------------------------------
# FIX 2 (npm): a registry-shaped candidate whose `resolved` was scrubbed must
# NOT be silently dropped -- it is tagged ``unverifiable`` so find_violations
# fails closed. Genuine non-registry forms stay excluded.
# ---------------------------------------------------------------------------


def test_parse_npm_lock_scrubbed_resolved_is_tagged_unverifiable():
    """A concrete-semver entry that is NOT link/file/git/workspace but has
    its ``resolved`` stripped is returned tagged ``unverifiable`` (fail
    closed), NOT dropped."""
    obj = {
        "packages": {
            "": {"name": "root", "version": "0.0.0"},
            "node_modules/evil": {"version": "6.6.6", "integrity": "sha512-z"},
        }
    }
    pkgs = guard.parse_npm_lock(obj)
    assert pkgs == [("evil", "6.6.6", None, "unverifiable")]


def test_parse_npm_lock_non_http_resolved_is_unverifiable():
    """A concrete-semver entry whose ``resolved`` is a non-``http(s)`` URL
    (scheme present but not http/https, e.g. ``ftp://``) is registry-shaped
    yet unverifiable -> tagged, not dropped."""
    obj = {
        "packages": {
            "node_modules/sneaky": {
                "version": "1.2.3",
                "resolved": "ftp://evil.example/sneaky-1.2.3.tgz",
            }
        }
    }
    pkgs = guard.parse_npm_lock(obj)
    assert pkgs == [
        ("sneaky", "1.2.3", "ftp://evil.example/sneaky-1.2.3.tgz", "unverifiable")
    ]


@pytest.mark.parametrize(
    ("meta", "why"),
    [
        ({"resolved": "link:../x", "link": True}, "link:true workspace"),
        ({"version": "1.0.0", "resolved": "file:../x-1.0.0.tgz"}, "file: tarball"),
        (
            {"version": "1.0.0", "resolved": "git+https://h/x.git#abc"},
            "git+ vcs dep",
        ),
        ({"version": "1.0.0", "resolved": "git://h/x.git"}, "git: vcs dep"),
        ({"version": "1.0.0", "resolved": "../packages/x"}, "workspace path"),
        ({"resolved": "https://r/x.tgz"}, "no version (alias/meta)"),
        ({"version": "not-semver", "resolved": "https://r/x.tgz"}, "non-semver"),
    ],
)
def test_parse_npm_lock_genuine_non_registry_forms_excluded(meta, why):
    """Genuine non-registry forms are excluded entirely (NOT tagged
    unverifiable) so a legitimate workspace/vcs/file lock is never
    false-flagged by the fail-closed rule."""
    obj = {"packages": {"node_modules/x": meta}}
    assert guard.parse_npm_lock(obj) == [], f"should be excluded: {why}"


def test_parse_npm_lock_root_entry_never_returned():
    """The root ``""`` entry is never returned, even with a version."""
    obj = {"packages": {"": {"version": "1.2.3", "resolved": "https://r/x"}}}
    assert guard.parse_npm_lock(obj) == []


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


@pytest.mark.parametrize("bad", [None, 123, 1.5, [1], {"a": 1}, True])
def test_iso_to_dt_non_string_raises_value_error_not_attribute_error(bad):
    """FIX 3 regression: a non-string timestamp must raise ``ValueError``
    (the documented clean failure every caller absorbs), NOT ``AttributeError``.

    A registry/lock returning ``time[version]`` as null/number/list/object
    previously hit ``s.strip()`` on a non-str and raised ``AttributeError``,
    which is NOT in ``npm_published_at``'s / ``_first_upload_time``'s except
    tuple -> the CI guard crashed instead of degrading to a clean
    None/warning (and, for a uv candidate, instead of becoming a violation).
    """
    with pytest.raises(ValueError, match="expected ISO 8601 timestamp string"):
        guard.iso_to_dt(bad)


def test_iso_to_dt_value_error_message_names_the_type():
    """The ValueError must name the offending type for debuggability."""
    with pytest.raises(ValueError, match="got NoneType"):
        guard.iso_to_dt(None)
    with pytest.raises(ValueError, match="got int"):
        guard.iso_to_dt(123)


def test_iso_to_dt_callers_absorb_value_error_consistently():
    """Every ``iso_to_dt`` caller already catches ``ValueError`` -> a
    malformed/odd registry or lock timestamp degrades to None/warning
    consistently (and, for a uv candidate, FIX 2 turns the resulting
    ``upload_time is None`` into a violation -- never a silent skip)."""
    # _first_upload_time absorbs it (-> None upload time).
    block = '\nname = "x"\nversion = "1.0.0"\nupload-time = 12345\n'
    assert guard._first_upload_time(block) is None


# ---------------------------------------------------------------------------
# find_violations — baseline / delta semantics
#
# A dependency only violates the policy if its pinned (name, version) is NOT
# present in the baseline lockfile (i.e. it was *added* or *version-changed*
# vs the baseline) AND it is younger than min_age. Dependencies unchanged
# from the baseline are grandfathered (the established lock is trusted; the
# threat is a *new/upgraded* fresh version entering). A baseline of ``None``
# means the lock did not exist at the base ref -> this run is
# *baseline-establishing*: every young dep is grandfathered (0 violations)
# but still surfaced for visibility. This mirrors Dependabot ``cooldown``.
# ---------------------------------------------------------------------------

NOW = _dt(2026, 5, 17, 12, 0, 0)
MIN_AGE = timedelta(days=7)

# Empty baseline sets: nothing was previously locked, but the lock *did*
# exist at the base ref (vs ``None`` which means it did not). Every pin is
# therefore "added" and a candidate for the age check.
EMPTY_BASE: set = set()


def _no_npm(name, version):  # pragma: no cover - injected, never called here
    raise AssertionError("npm lookup must not be called for uv-only cases")


@pytest.mark.parametrize(
    ("uploaded", "expect_violation"),
    [
        (NOW - timedelta(days=2), True),  # 2 days old, newly added -> too fresh
        (NOW - timedelta(days=30), False),  # 30 days old -> fine
    ],
)
def test_find_violations_uv_age_for_added_dep(uploaded, expect_violation):
    """An added dep (not in baseline) younger than min_age is a violation."""
    uv_pkgs = [("freshpkg", "1.0.0", uploaded, "registry")]
    violations, warnings, grandfathered = guard.find_violations(
        uv_pkgs,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert warnings == []
    assert grandfathered == []
    assert (len(violations) == 1) is expect_violation
    if expect_violation:
        v = violations[0]
        assert v.ecosystem == "uv"
        assert v.name == "freshpkg"
        assert v.version == "1.0.0"


def test_find_violations_uv_unchanged_from_baseline_is_grandfathered():
    """A young dep with the SAME (name, version) as baseline is NOT a
    violation -- it is grandfathered (and surfaced for visibility)."""
    uv_pkgs = [("vetted", "1.0.0", NOW - timedelta(days=1), "registry")]
    violations, warnings, grandfathered = guard.find_violations(
        uv_pkgs,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline={("vetted", "1.0.0")},
        npm_baseline=EMPTY_BASE,
    )
    assert violations == []
    assert warnings == []
    assert len(grandfathered) == 1
    assert grandfathered[0].name == "vetted"
    assert grandfathered[0].version == "1.0.0"


def test_find_violations_uv_baseline_none_is_establishing():
    """baseline=None (lock absent at base ref) -> establishing: even a very
    young added dep is grandfathered, never a violation."""
    uv_pkgs = [("brandnew", "0.1.0", NOW - timedelta(hours=1), "registry")]
    violations, warnings, grandfathered = guard.find_violations(
        uv_pkgs,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=None,
        npm_baseline=None,
    )
    assert violations == []
    assert warnings == []
    assert len(grandfathered) == 1
    assert grandfathered[0].name == "brandnew"


@pytest.mark.parametrize(
    ("old_ver", "new_ver", "uploaded", "expect_violation"),
    [
        # version changed, new version is young -> violation
        ("1.0.0", "2.0.0", NOW - timedelta(days=1), True),
        # version changed, new version is old enough -> no violation
        ("1.0.0", "2.0.0", NOW - timedelta(days=30), False),
    ],
)
def test_find_violations_uv_version_change(
    old_ver, new_ver, uploaded, expect_violation
):
    uv_pkgs = [("changing", new_ver, uploaded, "registry")]
    violations, warnings, grandfathered = guard.find_violations(
        uv_pkgs,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline={("changing", old_ver)},
        npm_baseline=EMPTY_BASE,
    )
    assert warnings == []
    assert (len(violations) == 1) is expect_violation
    # When old enough it is neither a violation nor grandfathered-young.
    if not expect_violation:
        assert grandfathered == []


@pytest.mark.parametrize("kind", [None, "editable", "virtual", "directory", "git"])
def test_find_violations_uv_non_registry_no_upload_time_is_ignored(kind):
    """A non-registry source (root/editable/virtual/directory/git) without an
    upload-time is never a violation -- even as a candidate -- because it is
    not subject to the registry-age policy at all."""
    violations, warnings, grandfathered = guard.find_violations(
        [("henry-castillo", "0.0.0", None, kind)],
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        # Empty baseline => this pin is "added" (a candidate); it must STILL
        # be ignored because it is not a registry source.
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert violations == []
    assert warnings == []
    assert grandfathered == []


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
    """The 7-day boundary for a newly added dep is exact and inclusive."""
    uv_pkgs = [("boundary", "2.0.0", NOW - delta, "registry")]
    violations, _, _ = guard.find_violations(
        uv_pkgs,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert (len(violations) == 1) is expect_violation


# ---------------------------------------------------------------------------
# FIX 2 (HIGH): the dependency-age guard must FAIL CLOSED for an unverifiable
# *registry* candidate (a tampered lock that stripped upload-time/resolved
# off a malicious added dep must NOT bypass the guard), WITHOUT
# false-flagging legitimate non-registry (editable/virtual/git/...) entries.
# ---------------------------------------------------------------------------


def test_find_violations_uv_registry_candidate_missing_upload_time_is_violation():
    """A registry-source CANDIDATE with NO upload-time is a hard violation
    (fail closed) -- not silently skipped as before.

    Old behavior: ``if uploaded is None: continue`` dropped it -> a
    hand-tampered lock that scrubbed ``upload-time`` off a fresh malicious
    added dep bypassed the guard entirely.
    """
    violations, warnings, grandfathered = guard.find_violations(
        [("evilpkg", "6.6.6", None, "registry")],
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,  # not in baseline => candidate
        npm_baseline=EMPTY_BASE,
    )
    assert warnings == []
    assert grandfathered == []
    assert len(violations) == 1
    v = violations[0]
    assert isinstance(v, guard.Unverifiable)
    assert v.ecosystem == "uv"
    assert v.name == "evilpkg"
    assert v.version == "6.6.6"
    rendered = v.render(MIN_AGE)
    assert "cannot verify age" in rendered
    assert "missing/invalid upload-time" in rendered
    assert "evilpkg==6.6.6" in rendered


def test_find_violations_uv_malformed_upload_time_is_violation():
    """A registry candidate whose ``upload-time`` is unparseable (parse ->
    None via FIX 3's ValueError absorbed by ``_first_upload_time``) is the
    SAME fail-closed violation as a missing one -- coherent with FIX 3."""
    # _first_upload_time returns None for a non-timestamp value, so the
    # find_violations input mirrors that (uploaded is None) but the package
    # IS a registry source -> violation, not skip.
    bad_block = (
        "\n[[package]]\n"
        'name = "badts"\n'
        'version = "1.0.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'sdist = { url = "https://e/b.tgz", upload-time = "not-a-ts" }\n'
    )
    parsed = guard.parse_uv_lock("version=1\n" + bad_block)
    assert parsed == [("badts", "1.0.0", None, "registry")]
    violations, _, _ = guard.find_violations(
        parsed,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert len(violations) == 1
    assert isinstance(violations[0], guard.Unverifiable)
    assert violations[0].name == "badts"


def test_parse_uv_lock_upload_time_typo_key_yields_none_time():
    """A typo'd ``uploadtime``/``upload_time`` key (NOT the real
    ``upload-time``) leaves the time unparsed (None) -> a registry candidate
    with that typo is a FIX-2 violation, not a silent pass."""
    block = (
        "version=1\n"
        "\n[[package]]\n"
        'name = "typo"\n'
        'version = "2.0.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'sdist = { url = "https://e/t.tgz", uploadtime = "2020-01-01T00:00:00Z" }\n'
    )
    parsed = guard.parse_uv_lock(block)
    assert parsed == [("typo", "2.0.0", None, "registry")]
    violations, _, _ = guard.find_violations(
        parsed,
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert len(violations) == 1
    assert isinstance(violations[0], guard.Unverifiable)


@pytest.mark.parametrize("kind", [None, "editable", "virtual", "directory", "git"])
def test_find_violations_uv_non_registry_candidate_missing_time_not_violation(kind):
    """A NON-registry pkg (editable/virtual/directory/git/source-less) as a
    *candidate* with no upload-time is NOT a violation -- it legitimately has
    no registry publish time and is not subject to the age policy. This is
    the no-false-positive half of fail-closed."""
    violations, warnings, grandfathered = guard.find_violations(
        [("localdep", "0.0.0", None, kind)],
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,  # candidate, yet still ignored
        npm_baseline=EMPTY_BASE,
    )
    assert violations == []
    assert warnings == []
    assert grandfathered == []


def test_find_violations_uv_unchanged_registry_missing_time_grandfathered():
    """An UNCHANGED-from-baseline registry pin with no upload-time is NOT a
    violation -- only *candidates* are enforced, so an already-vetted lock
    pin missing a time is grandfathered (not retroactively flagged)."""
    violations, warnings, grandfathered = guard.find_violations(
        [("oldvetted", "1.0.0", None, "registry")],
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline={("oldvetted", "1.0.0")},  # in baseline => NOT a candidate
        npm_baseline=EMPTY_BASE,
    )
    assert violations == []
    assert warnings == []
    assert grandfathered == []


def test_find_violations_uv_establishing_missing_time_not_violation():
    """On a baseline-establishing run (uv_baseline=None) a registry pin with
    no upload-time is NOT a violation (nothing is a candidate while
    establishing)."""
    violations, _, _ = guard.find_violations(
        [("fresh", "9.9.9", None, "registry")],
        [],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=None,
        npm_baseline=None,
    )
    assert violations == []


def test_find_violations_npm_scrubbed_resolved_candidate_is_violation():
    """An npm ``unverifiable`` (scrubbed-resolved) CANDIDATE is a hard
    violation (fail closed) -- the registry is NOT consulted (it is a
    structural tamper indicator, not a transient network error)."""
    violations, warnings, grandfathered = guard.find_violations(
        [],
        [("evilnpm", "2.0.0", None, "unverifiable")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,  # must NOT be called
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert warnings == []
    assert grandfathered == []
    assert len(violations) == 1
    v = violations[0]
    assert isinstance(v, guard.Unverifiable)
    assert v.ecosystem == "npm"
    assert v.name == "evilnpm"
    r = v.render(MIN_AGE)
    assert "cannot verify age" in r
    assert "no registry `resolved`" in r


def test_find_violations_npm_scrubbed_resolved_unchanged_is_not_violation():
    """An ``unverifiable`` npm pin that is UNCHANGED from baseline is trusted
    (only candidates enforced) -- not retroactively flagged."""
    violations, _, _ = guard.find_violations(
        [],
        [("legacy", "1.0.0", None, "unverifiable")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,
        npm_baseline={("legacy", "1.0.0")},
    )
    assert violations == []


def test_find_violations_npm_scrubbed_resolved_establishing_not_violation():
    """On an establishing npm run an ``unverifiable`` pin is not a violation
    (nothing is a candidate while establishing)."""
    violations, _, _ = guard.find_violations(
        [],
        [("legacy", "1.0.0", None, "unverifiable")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=_no_npm,
        uv_baseline=None,
        npm_baseline=None,
    )
    assert violations == []


# ---------------------------------------------------------------------------
# find_violations — npm side (delta semantics)
# ---------------------------------------------------------------------------


def test_find_violations_npm_fresh_added_is_violation():
    def fetch(name, version):
        assert (name, version) == ("freshnpm", "1.2.3")
        return NOW - timedelta(days=1)

    violations, warnings, grandfathered = guard.find_violations(
        [],
        [("freshnpm", "1.2.3", "https://r/freshnpm-1.2.3.tgz", "registry")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=fetch,
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert warnings == []
    assert grandfathered == []
    assert len(violations) == 1
    assert violations[0].ecosystem == "npm"
    assert violations[0].name == "freshnpm"


def test_find_violations_npm_unchanged_from_baseline_is_grandfathered():
    """A young npm dep unchanged from baseline is grandfathered, and the
    registry is still consulted only for *candidate* (new/changed) deps."""
    violations, warnings, grandfathered = guard.find_violations(
        [],
        [("vettednpm", "4.5.6", "https://r/vettednpm-4.5.6.tgz", "registry")],
        now=NOW,
        min_age=MIN_AGE,
        # Unchanged deps must NOT trigger a registry lookup.
        npm_published_at=_no_npm,
        uv_baseline=EMPTY_BASE,
        npm_baseline={("vettednpm", "4.5.6")},
    )
    assert violations == []
    assert warnings == []
    # Unchanged-from-baseline deps are silently trusted (no lookup, so no
    # publish time to surface) -- they are not in the grandfathered list.
    assert grandfathered == []


def test_find_violations_npm_old_added_is_clean():
    violations, warnings, grandfathered = guard.find_violations(
        [],
        [("oldnpm", "9.9.9", "https://r/oldnpm-9.9.9.tgz", "registry")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=lambda n, v: NOW - timedelta(days=60),
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert violations == []
    assert warnings == []
    assert grandfathered == []


def test_find_violations_npm_lookup_failure_on_candidate_is_warning():
    """Fail-open for transient registry errors: a None lookup on a candidate
    (added/changed) dep is a WARNING, not a violation."""
    violations, warnings, grandfathered = guard.find_violations(
        [],
        [("mystery", "0.1.0", "https://r/mystery-0.1.0.tgz", "registry")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=lambda n, v: None,
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
    )
    assert violations == []
    assert grandfathered == []
    assert len(warnings) == 1
    assert "mystery" in warnings[0]
    assert "0.1.0" in warnings[0]


def test_find_violations_npm_baseline_none_is_establishing():
    """baseline=None for npm -> establishing: a young added npm dep is
    grandfathered (registry still consulted to surface it), not a violation."""
    violations, warnings, grandfathered = guard.find_violations(
        [],
        [("freshnpm", "2.0.0", "https://r/freshnpm-2.0.0.tgz", "registry")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=lambda n, v: NOW - timedelta(days=1),
        uv_baseline=None,
        npm_baseline=None,
    )
    assert violations == []
    assert warnings == []
    assert len(grandfathered) == 1
    assert grandfathered[0].ecosystem == "npm"
    assert grandfathered[0].name == "freshnpm"


@pytest.mark.parametrize(
    ("delta", "expect_violation"),
    [
        (timedelta(days=7), False),
        (timedelta(days=7) - timedelta(seconds=1), True),
        (timedelta(days=7) + timedelta(seconds=1), False),
    ],
)
def test_find_violations_npm_boundary_is_pinned(delta, expect_violation):
    violations, warnings, _ = guard.find_violations(
        [],
        [("npmboundary", "3.0.0", "https://r/npmboundary-3.0.0.tgz", "registry")],
        now=NOW,
        min_age=MIN_AGE,
        npm_published_at=lambda n, v: NOW - delta,
        uv_baseline=EMPTY_BASE,
        npm_baseline=EMPTY_BASE,
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


@pytest.mark.parametrize("v", [None, 123, [1], {"a": 1}, True])
def test_npm_published_at_non_string_time_value_returns_none(v):
    """FIX 3 regression: a registry returning ``time[version]`` as
    null/number/list/object must yield None (fail-open warning), NOT crash.

    Before FIX 3, ``iso_to_dt(times[version])`` -> ``s.strip()`` raised
    ``AttributeError`` which is NOT in ``npm_published_at``'s
    ``except (URLError, OSError, ValueError, KeyError, TypeError)`` tuple, so
    ``find_violations``/``main`` crashed instead of recording a warning.
    """
    body = json.dumps({"time": {"1.0.0": v}}).encode()

    def opener(url, timeout=None):
        return _FakeResp(body)

    assert guard.npm_published_at("pkg", "1.0.0", opener=opener) is None


# ---------------------------------------------------------------------------
# load_baseline — git read isolation with an injectable runner
# ---------------------------------------------------------------------------


def test_load_baseline_parses_uv_set_from_runner_content():
    """A runner that returns lock content yields the parsed (name, version)
    set. The runner is called with (base_ref, path)."""
    seen = {}

    def runner(base_ref, path):
        seen["base_ref"] = base_ref
        seen["path"] = path
        return UV_LOCK_SAMPLE

    result = guard.load_baseline("origin/main", "uv.lock", kind="uv", runner=runner)
    assert seen == {"base_ref": "origin/main", "path": "uv.lock"}
    assert ("annotated-doc", "0.0.4") in result
    assert ("click", "8.4.0") in result


def test_load_baseline_parses_npm_set_from_runner_content():
    def runner(base_ref, path):
        return json.dumps(NPM_LOCK_SAMPLE)

    result = guard.load_baseline(
        "origin/main",
        "packages/npm/package-lock.json",
        kind="npm",
        runner=runner,
    )
    assert ("typescript", "5.7.2") in result
    assert ("@types/node", "25.8.0") in result


def test_load_baseline_runner_raising_means_absent_returns_none():
    """If the path/ref does not exist at the base ref the runner raises;
    load_baseline maps that to None (== baseline-establishing), never an
    exception (robust for a pre-commit run with no fetched origin/main)."""

    def runner(base_ref, path):
        raise guard.BaselineUnavailable("git show failed: bad ref or path")

    assert (
        guard.load_baseline("origin/main", "uv.lock", kind="uv", runner=runner) is None
    )


def test_load_baseline_npm_invalid_json_yields_empty_set_not_none():
    """A present-but-unparseable npm baseline is an empty set (the lock
    existed at base, so pins are still "added"), distinct from None."""

    def runner(base_ref, path):
        return "{not json"

    result = guard.load_baseline(
        "origin/main", "p/lock.json", kind="npm", runner=runner
    )
    assert result == set()


def test_git_show_runner_returns_none_on_called_process_error(monkeypatch):
    """The default runner shells out to ``git show``; a non-zero exit (ref
    or path absent) is raised as BaselineUnavailable so load_baseline -> None.
    """

    def fake_check_output(cmd, *a, **k):
        assert cmd[:2] == ["git", "show"]
        raise subprocess.CalledProcessError(128, cmd, b"", b"fatal: bad ref")

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    with pytest.raises(guard.BaselineUnavailable):
        guard._git_show("origin/main", "uv.lock")


def test_git_show_runner_returns_content_on_success(monkeypatch):
    def fake_check_output(cmd, *a, **k):
        assert cmd == ["git", "show", "origin/main:uv.lock"]
        return b"version = 1\n"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    assert guard._git_show("origin/main", "uv.lock") == "version = 1\n"


def test_git_show_runner_oserror_means_baseline_unavailable(monkeypatch):
    """git binary missing / unexecutable (OSError, e.g. FileNotFoundError)
    is mapped to BaselineUnavailable, NOT a raw crash, so load_baseline can
    degrade to establishing in an environment without git."""

    def fake_check_output(cmd, *a, **k):
        raise FileNotFoundError("git: command not found")

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    with pytest.raises(guard.BaselineUnavailable):
        guard._git_show("origin/main", "uv.lock")


def test_load_baseline_npm_valid_json_non_dict_yields_empty_set_not_none():
    """A present npm baseline that is valid JSON but not an object (e.g. a
    JSON array ``[]``) is an empty set (the lock existed at base, so every
    current pin is still 'added'), distinct from None (== establishing)."""

    def runner(base_ref, path):
        return "[]"

    result = guard.load_baseline(
        "origin/main", "p/lock.json", kind="npm", runner=runner
    )
    assert result == set()
    assert result is not None


# ---------------------------------------------------------------------------
# iso_to_dt — naive + non-UTC offset normalization (Py3.10-safe target)
# ---------------------------------------------------------------------------


def test_iso_to_dt_naive_timestamp_is_assumed_utc():
    """A timestamp with NO timezone is treated as UTC (tzinfo == utc)."""
    got = guard.iso_to_dt("2025-11-10T22:07:42.062")
    assert got.tzinfo == timezone.utc
    assert got == _dt(2025, 11, 10, 22, 7, 42, 62000)


def test_iso_to_dt_non_utc_offset_is_normalized_to_utc():
    """A non-UTC offset (e.g. +05:00) is normalized so the result is UTC."""
    got = guard.iso_to_dt("2025-11-10T22:07:42+05:00")
    assert got.utcoffset() == timedelta(0)
    # 22:07:42 +05:00 == 17:07:42 UTC
    assert got == _dt(2025, 11, 10, 17, 7, 42)


# ---------------------------------------------------------------------------
# load_baseline — repo-relative lock path resolution (supply-chain guard:
# an absolute / non-repo-relative lock path must NOT silently false-pass as
# "establishing" — that would grandfather a fresh malicious dep).
# ---------------------------------------------------------------------------


def test_load_baseline_absolute_in_repo_path_resolves_not_false_establishing():
    """REGRESSION: an ABSOLUTE path to an in-repo lock that DOES exist at the
    base ref must resolve the real baseline, NOT degrade to None.

    Before the fix ``git show <ref>:<absolute-path>`` always failed ->
    BaselineUnavailable -> None -> the run silently became
    'baseline-establishing' (exit 0), grandfathering a fresh malicious dep.
    Using ``HEAD`` (this branch tip, which DOES commit ``uv.lock``) as a
    stand-in baseline ref + the repo's real absolute ``uv.lock`` path, the
    baseline must come back as a non-empty pin set.
    """
    abs_uv_lock = str(_REPO_ROOT / "uv.lock")
    result = guard.load_baseline("HEAD", abs_uv_lock, kind="uv")
    assert result is not None, (
        "absolute in-repo lock path falsely degraded to None "
        "(== baseline-establishing false-pass)"
    )
    assert len(result) > 0


def test_load_baseline_path_outside_repo_raises_clear_error():
    """A lock path OUTSIDE the git repo is a hard, explicit error (non-zero),
    never a silent 'establishing' pass."""
    with pytest.raises(ValueError, match="outside"):
        guard.load_baseline("HEAD", "/etc/hostname", kind="uv")


def test_main_absolute_in_repo_lock_does_not_false_establish(capsys):
    """End-to-end: ``main`` with the repo's real ABSOLUTE ``uv.lock`` and
    ``--base-ref HEAD`` (which commits uv.lock) must NOT print an
    'establishing' baseline line and must NOT exit 0 via the
    establishing/no-committed-lock path (it resolves the real baseline).
    """
    abs_uv_lock = str(_REPO_ROOT / "uv.lock")
    rc = guard.main(["--uv-lock", abs_uv_lock, "--base-ref", "HEAD", "--skip-npm"])
    out = capsys.readouterr().out
    low = out.lower()
    assert "establish" not in low, (
        f"absolute in-repo lock path falsely reported establishing:\n{out}"
    )
    assert "no committed lock at base" not in low
    # Baseline resolved against HEAD == current pins -> nothing newly
    # added/upgraded -> a genuine clean pass (delta mode, not establishing).
    assert rc == 0
    assert "delta vs HEAD" in out


# ---------------------------------------------------------------------------
# main — baseline / establishing semantics
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


def _baseline_absent(base_ref, path, *, kind, runner=None):
    """Stand-in for load_baseline when the lock is absent at the base ref."""
    return None


def _baseline_from(*pairs):
    """Build a load_baseline stand-in returning a fixed (name, version) set
    regardless of which lock/kind is requested."""

    def _loader(base_ref, path, *, kind, runner=None):
        return set(pairs)

    return _loader


def test_main_establishing_run_grandfathers_young_and_exits_zero(
    tmp_path, monkeypatch, capsys
):
    """THIS PR's scenario: no uv.lock at origin/main -> baseline absent ->
    establishing. A very fresh dep is grandfathered, exit 0, and the young
    dep is reported on a clear INFO line for visibility."""
    fresh = datetime.now(UTC) - timedelta(hours=12)
    ts = fresh.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    monkeypatch.setattr(guard, "load_baseline", _baseline_absent)

    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    low = out.lower()
    assert "establish" in low
    assert "veryfresh==9.9.9" in out
    # No FAIL on an establishing run.
    assert "FAIL" not in out


def test_main_clean_returns_zero(tmp_path, monkeypatch, capsys):
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    # Baseline equals the current pins -> everything grandfathered, clean.
    monkeypatch.setattr(
        guard,
        "load_baseline",
        _baseline_from(("annotated-doc", "0.0.4"), ("click", "8.4.0")),
    )
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK" in out or "no violations" in out.lower()


def test_main_added_young_dep_returns_one_and_reports(tmp_path, monkeypatch, capsys):
    """Baseline present and does NOT contain the pin (a future added/upgraded
    dep) and it is <7d old -> hard failure, exit 1."""
    fresh = datetime.now(UTC) - timedelta(hours=12)
    ts = fresh.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    # Baseline has some *other* package, so veryfresh==9.9.9 is "added".
    monkeypatch.setattr(
        guard, "load_baseline", _baseline_from(("something-else", "1.0.0"))
    )
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "veryfresh==9.9.9" in out
    assert "< 7d" in out
    assert "FAIL" in out


def test_main_added_dep_old_enough_is_clean(tmp_path, monkeypatch, capsys):
    """A newly added dep that is already >=7d old does not fail."""
    old = datetime.now(UTC) - timedelta(days=30)
    ts = old.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    monkeypatch.setattr(
        guard, "load_baseline", _baseline_from(("something-else", "1.0.0"))
    )
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK" in out or "no violations" in out.lower()


def test_main_grandfathered_young_dep_unchanged_is_clean(tmp_path, monkeypatch, capsys):
    """A young dep whose (name, version) IS in the baseline (unchanged) does
    not fail even though it is <7d old."""
    fresh = datetime.now(UTC) - timedelta(hours=12)
    ts = fresh.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    monkeypatch.setattr(guard, "load_baseline", _baseline_from(("veryfresh", "9.9.9")))
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "FAIL" not in out


def test_main_base_ref_is_passed_to_load_baseline(tmp_path, monkeypatch, capsys):
    """--base-ref is honored and forwarded to load_baseline."""
    seen = {}

    def loader(base_ref, path, *, kind, runner=None):
        seen.setdefault("refs", []).append(base_ref)
        # Fall through -> returns None == baseline-establishing.

    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    monkeypatch.setattr(guard, "load_baseline", loader)
    rc = guard.main(
        [
            "--uv-lock",
            str(uv_lock),
            "--npm-lock",
            str(npm_lock),
            "--skip-npm",
            "--base-ref",
            "origin/develop",
        ]
    )
    assert rc == 0
    assert seen["refs"] == ["origin/develop"]
    capsys.readouterr()


def test_main_skip_npm_ignores_npm_entirely(tmp_path, monkeypatch, capsys):
    # An npm package that WOULD be a violation if checked.
    def boom(*a, **k):  # pragma: no cover - must never run under --skip-npm
        raise AssertionError("npm registry must not be queried with --skip-npm")

    monkeypatch.setattr(guard, "npm_published_at", boom)
    monkeypatch.setattr(guard, "load_baseline", _baseline_absent)
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    assert rc == 0
    capsys.readouterr()


def test_main_npm_added_violation_via_injected_fetcher(tmp_path, monkeypatch, capsys):
    """A future npm bump: pin not in baseline + <7d via the registry -> fail."""
    fresh = datetime.now(UTC) - timedelta(days=1)
    monkeypatch.setattr(guard, "npm_published_at", lambda n, v, **k: fresh)
    # uv baseline matches its pins; npm baseline is empty so npm pins are
    # "added" candidates and get the registry check.
    monkeypatch.setattr(
        guard,
        "load_baseline",
        _baseline_from(("annotated-doc", "0.0.4"), ("click", "8.4.0")),
    )
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    rc = guard.main(["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "typescript==5.7.2" in out


def test_main_npm_registry_error_is_warning_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(guard, "npm_published_at", lambda n, v, **k: None)
    # Establishing so uv pins don't fail; npm candidates still get looked up
    # (registry error -> warning, not violation, not blocked).
    monkeypatch.setattr(guard, "load_baseline", _baseline_absent)
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    rc = guard.main(["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "warning" in out.lower()
    assert "typescript" in out


def test_main_missing_current_lock_files_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(guard, "load_baseline", _baseline_absent)
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


def test_main_min_age_days_is_honored(tmp_path, monkeypatch, capsys):
    # Added package uploaded 10 days ago: fine at default 7, fails at 14.
    ten_days = datetime.now(UTC) - timedelta(days=10)
    ts = ten_days.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    monkeypatch.setattr(
        guard, "load_baseline", _baseline_from(("something-else", "1.0.0"))
    )

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


# ---------------------------------------------------------------------------
# --min-age-days validation: a security control must not silently no-op at
# 0 or a negative value (min_age = timedelta(days=0) would make EVERYTHING
# old enough -> every fresh dep silently passes).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["0", "-1", "-7"])
def test_main_min_age_days_below_one_is_rejected(bad, tmp_path, monkeypatch, capsys):
    """``--min-age-days < 1`` must hard-fail (argparse error, exit code 2),
    NOT silently disable the guard."""
    monkeypatch.setattr(guard, "load_baseline", _baseline_absent)
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    with pytest.raises(SystemExit) as exc:
        guard.main(
            [
                "--uv-lock",
                str(uv_lock),
                "--npm-lock",
                str(npm_lock),
                "--skip-npm",
                "--min-age-days",
                bad,
            ]
        )
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "min-age-days" in err
    assert ">= 1" in err or "at least 1" in err


def test_main_min_age_days_one_is_accepted(tmp_path, monkeypatch, capsys):
    """The boundary value 1 is still valid (>= 1)."""
    monkeypatch.setattr(guard, "load_baseline", _baseline_absent)
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, NPM_LOCK_SAMPLE)
    rc = guard.main(
        [
            "--uv-lock",
            str(uv_lock),
            "--npm-lock",
            str(npm_lock),
            "--skip-npm",
            "--min-age-days",
            "1",
        ]
    )
    assert rc == 0
    capsys.readouterr()


def test_main_report_text_is_exact_for_added_uv_violation(
    tmp_path, monkeypatch, capsys
):
    uploaded = datetime.now(UTC) - timedelta(hours=24)
    ts = uploaded.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    uv_lock, npm_lock = _write_locks(tmp_path, _FRESH_UV.format(ts=ts), NPM_LOCK_SAMPLE)
    monkeypatch.setattr(
        guard, "load_baseline", _baseline_from(("something-else", "1.0.0"))
    )
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


# ---------------------------------------------------------------------------
# FIX 2 end-to-end via main(): a baseline-present run with an injected ADDED
# registry dep whose age cannot be verified must EXIT 1 (fail closed), not
# print "OK"/"establishing". And THIS PR's real establishing run still exits 0.
# ---------------------------------------------------------------------------

# A registry-source uv package with NO upload-time (tampered: the sdist/wheel
# upload-time was stripped after `uv add`).
_TAMPERED_UV_NO_UPLOAD_TIME = """\
[[package]]
name = "tampered"
version = "9.9.9"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://e/t.tgz" }
"""


def test_main_added_registry_dep_without_upload_time_exits_one(
    tmp_path, monkeypatch, capsys
):
    """Post-merge style: baseline present (HEAD-like) and does NOT contain the
    pin (added) and its ``upload-time`` was scrubbed -> the guard FAILS CLOSED
    (exit 1, FAIL line), it does NOT print OK/establishing.

    Old behavior: a registry pin with no upload-time was ``continue``-skipped
    so this tampered added dep slipped past the guard with exit 0.
    """
    uv_lock, npm_lock = _write_locks(
        tmp_path, _TAMPERED_UV_NO_UPLOAD_TIME, NPM_LOCK_SAMPLE
    )
    monkeypatch.setattr(
        guard, "load_baseline", _baseline_from(("something-else", "1.0.0"))
    )
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 1, f"expected fail-closed exit 1, got {rc}:\n{out}"
    assert "FAIL" in out
    assert "tampered==9.9.9" in out
    assert "cannot verify age" in out
    assert "OK:" not in out
    assert "establish" not in out.lower()


def test_main_tampered_added_dep_unchanged_from_baseline_is_clean(
    tmp_path, monkeypatch, capsys
):
    """No-false-positive guard: if that same upload-time-less registry pin is
    UNCHANGED from baseline it is grandfathered (only candidates enforced)."""
    uv_lock, npm_lock = _write_locks(
        tmp_path, _TAMPERED_UV_NO_UPLOAD_TIME, NPM_LOCK_SAMPLE
    )
    monkeypatch.setattr(guard, "load_baseline", _baseline_from(("tampered", "9.9.9")))
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "FAIL" not in out


def test_main_added_npm_dep_with_scrubbed_resolved_exits_one(
    tmp_path, monkeypatch, capsys
):
    """An ADDED npm dep that is registry-shaped (concrete semver) but whose
    ``resolved`` was scrubbed -> fail closed (exit 1), npm registry NOT hit."""

    def boom(*a, **k):  # the structural tamper must not need the network
        raise AssertionError("registry must not be queried for unverifiable")

    npm_obj = {
        "name": "x",
        "version": "0.0.0",
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "x", "version": "0.0.0"},
            "node_modules/evilnpm": {"version": "3.3.3", "integrity": "sha512-q"},
        },
    }
    uv_lock, npm_lock = _write_locks(tmp_path, UV_LOCK_SAMPLE, npm_obj)
    monkeypatch.setattr(guard, "npm_published_at", boom)
    # uv baseline matches its pins (no uv violation); npm baseline present and
    # WITHOUT evilnpm -> evilnpm is an added candidate.
    monkeypatch.setattr(
        guard,
        "load_baseline",
        _baseline_from(("annotated-doc", "0.0.4"), ("click", "8.4.0")),
    )
    rc = guard.main(["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock)])
    out = capsys.readouterr().out
    assert rc == 1, f"expected fail-closed exit 1, got {rc}:\n{out}"
    assert "FAIL" in out
    assert "evilnpm@3.3.3" in out or "evilnpm==3.3.3" in out
    assert "cannot verify age" in out


def test_main_genuine_non_registry_uv_dep_does_not_false_fail(
    tmp_path, monkeypatch, capsys
):
    """A legitimate editable/virtual/git uv entry (no upload-time, NOT a
    registry source) as an added pin must NOT fail the guard -- the
    fail-closed rule must not false-positive a normal local/vcs lock shape."""
    local_uv = """\
[[package]]
name = "mylocaltool"
source = { editable = "." }

[[package]]
name = "somevcs"
version = "1.0.0"
source = { git = "https://example/repo.git" }

[[package]]
name = "avirtual"
version = "2.0.0"
source = { virtual = "." }
"""
    uv_lock, npm_lock = _write_locks(tmp_path, local_uv, NPM_LOCK_SAMPLE)
    # Baseline present but does NOT contain these -> they are "added"
    # candidates; they must still be ignored (non-registry sources).
    monkeypatch.setattr(guard, "load_baseline", _baseline_from(("unrelated", "0.0.1")))
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 0, f"legitimate non-registry lock false-failed:\n{out}"
    assert "FAIL" not in out
    assert "cannot verify age" not in out


def test_main_this_pr_establishing_run_still_exits_zero_with_no_committed_lock(
    tmp_path, monkeypatch, capsys
):
    """THIS PR: origin/main has no committed uv.lock -> baseline absent ->
    establishing. Even the tampered (no upload-time) registry pin is
    grandfathered, exit 0 -- the fail-closed rule only bites a *candidate*
    (post-establishing delta), never the establishing run itself."""
    uv_lock, npm_lock = _write_locks(
        tmp_path, _TAMPERED_UV_NO_UPLOAD_TIME, NPM_LOCK_SAMPLE
    )
    monkeypatch.setattr(guard, "load_baseline", _baseline_absent)
    rc = guard.main(
        ["--uv-lock", str(uv_lock), "--npm-lock", str(npm_lock), "--skip-npm"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "FAIL" not in out
    assert "establish" in out.lower()
