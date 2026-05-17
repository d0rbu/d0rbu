#!/usr/bin/env python3
"""Rolling minimum age guard for *newly added/upgraded* deps (uv + npm).

Neither ``uv`` nor ``npm`` has a *rolling* minimum-release-age setting at the
lockfile layer (Dependabot's ``cooldown`` only gates *its own* PRs, not
arbitrary manual/Dependabot lock bumps once merged). This script provides that
missing guard with the same semantics as Dependabot ``cooldown``: a dependency
whose pinned ``(name, version)`` is **newly added or version-changed** versus a
baseline lockfile must have been published at least ``MIN_AGE_DAYS`` (default
7) ago. Dependencies **unchanged** from the baseline are grandfathered -- the
already-committed, already-vetted lock is the trusted baseline; the
supply-chain threat is a *new or upgraded* fresh version entering, not a pin
that was already there.

Baseline
--------
The baseline is the lockfile content at ``--base-ref`` (default
``origin/main``), read with ``git show <base-ref>:<path>``. If that path does
**not** exist at the base ref (e.g. the very first PR that introduces the
lockfiles -- ``main`` has no committed ``uv.lock`` yet), the run is
*baseline-establishing*: the current pins become the accepted baseline, so
there are **no violations** (exit 0). The young deps are still printed on a
clear INFO line so they are visible. A ``git show`` that fails for any reason
(unknown ref, no fetched ``origin/main`` in a pre-commit run, ...) is treated
as "baseline absent -> establishing -> pass", never a crash.

Design notes
------------
* **Stdlib only**, and must run under Python 3.10 -- so ``tomllib`` (3.11+)
  is intentionally NOT used; ``uv.lock`` is parsed with a small, robust
  ``[[package]]``-block scanner instead of a TOML library.
* Pure, side-effect-free functions with injectable ``now`` / fetcher / git
  runner so the behaviour is deterministic and unit-testable without a real
  network and without touching the real repository.

Policy
------
* **uv**: ``uv.lock`` records an ``upload-time`` for every registry package,
  so the age of a candidate is always positively decidable *offline*. A
  candidate (added/changed pin) newer than ``min_age`` is a hard
  **violation**. The root/editable project (no ``upload-time``) is skipped.
* **npm**: ``package-lock.json`` has no timestamps, so the publish time of a
  *candidate* is fetched from the npm registry. Pins unchanged from the
  baseline are trusted without a lookup. A candidate positively newer than
  ``min_age`` is a **violation**. If the lookup fails (network/registry/parse
  error) it is a **warning**, not a violation -- a deliberate, documented
  fail-open so a flaky registry does not break CI. A *confirmed* too-fresh
  candidate is never silently passed.

This file lives outside the ``henry_castillo`` package on purpose, so it is
not measured by the package's 100% coverage gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

MIN_AGE_DAYS = 7
NPM_REGISTRY = "https://registry.npmjs.org"
DEFAULT_UV_LOCK = "uv.lock"
DEFAULT_NPM_LOCK = "packages/npm/package-lock.json"
DEFAULT_BASE_REF = "origin/main"

UvPackage = tuple[str, str, "datetime | None"]
NpmPackage = tuple[str, str]
PinSet = set[tuple[str, str]]
Opener = Callable[..., Any]
NpmFetcher = Callable[..., "datetime | None"]
GitRunner = Callable[[str, str], str]


class BaselineUnavailable(Exception):  # noqa: N818 - domain name, not an error condition
    """The baseline lockfile could not be read at the base ref.

    Raised by the git runner when ``git show <ref>:<path>`` fails (unknown
    ref/path, no fetched ``origin/main`` in a bare pre-commit run, ...).
    ``load_baseline`` maps this to ``None`` == *baseline-establishing*, so the
    guard passes instead of crashing.
    """


@dataclass(frozen=True)
class Violation:
    """A dependency that is younger than the minimum age.

    Used both for hard violations (a *candidate* -- added/changed vs baseline
    -- that is too fresh) and for the informational "grandfathered young"
    list surfaced for visibility on an establishing/unchanged run.
    """

    ecosystem: str
    name: str
    version: str
    published: datetime
    age: timedelta

    def render(self, min_age: timedelta) -> str:
        hours = int(self.age.total_seconds() // 3600)
        days = int(min_age.total_seconds() // 86400)
        return (
            f"[{self.ecosystem}] {self.name}=={self.version} "
            f"published {self.published.isoformat()} "
            f"({hours}h old, < {days}d)"
        )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def iso_to_dt(s: str) -> datetime:
    """Parse an RFC3339 / ISO-8601 timestamp into a tz-aware UTC datetime.

    Handles the ``Z`` (Zulu) suffix, which ``datetime.fromisoformat`` does
    not accept on Python 3.10. Naive inputs are assumed to be UTC.
    """
    text = s.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _scalar(line: str, key: str) -> str | None:
    """Return the quoted string value of ``key = "..."`` on ``line``."""
    stripped = line.strip()
    prefix = f"{key} = "
    if not stripped.startswith(prefix):
        return None
    rest = stripped[len(prefix) :].strip()
    if not rest.startswith('"'):
        return None
    end = rest.find('"', 1)
    if end == -1:
        return None
    return rest[1:end]


def _first_upload_time(block: str) -> datetime | None:
    """First ``upload-time = "..."`` anywhere in a package block.

    In ``uv.lock`` the timestamp is embedded inside the ``sdist = { ... }``
    inline table and each ``wheels = [ { ... } ]`` entry, not as a
    package-level key. The sdist (or, for wheel-only packages, the first
    wheel) upload time is the version's publication time.
    """
    marker = "upload-time = "
    idx = block.find(marker)
    if idx == -1:
        return None
    rest = block[idx + len(marker) :]
    if not rest.startswith('"'):
        return None
    end = rest.find('"', 1)
    if end == -1:
        return None
    try:
        return iso_to_dt(rest[1:end])
    except ValueError:
        return None


def parse_uv_lock(text: str) -> list[UvPackage]:
    """Extract ``(name, version, upload_time | None)`` from ``uv.lock`` text.

    Iterates ``[[package]]`` blocks. ``name``/``version`` are read regardless
    of key order; ``upload_time`` is the first embedded ``upload-time`` in the
    block (``None`` for the root/editable project and path deps).
    """
    blocks = text.split("[[package]]")
    packages: list[UvPackage] = []
    for block in blocks[1:]:
        name: str | None = None
        version: str | None = None
        for line in block.splitlines():
            if name is None:
                got = _scalar(line, "name")
                if got is not None:
                    name = got
                    continue
            if version is None:
                got = _scalar(line, "version")
                if got is not None:
                    version = got
            if name is not None and version is not None:
                break
        if name is None:
            continue
        packages.append((name, version or "", _first_upload_time(block)))
    return packages


def parse_npm_lock(json_obj: dict[str, Any]) -> list[NpmPackage]:
    """Extract ``(name, version)`` for registry deps from a v3 lockfile.

    Only ``packages`` entries with a concrete ``version`` and a registry
    ``resolved`` URL are returned. The root ``""`` entry and
    ``link:``/``file:``/workspace entries are skipped.
    """
    packages = json_obj.get("packages")
    if not isinstance(packages, dict):
        return []
    result: list[NpmPackage] = []
    for path, meta in packages.items():
        if not path or not isinstance(meta, dict):
            continue
        version = meta.get("version")
        resolved = meta.get("resolved")
        if not isinstance(version, str) or not isinstance(resolved, str):
            continue
        if not resolved.startswith(("http://", "https://")):
            continue
        name = path.split("node_modules/")[-1]
        result.append((name, version))
    return result


# ---------------------------------------------------------------------------
# Baseline (git-isolated, injectable runner)
# ---------------------------------------------------------------------------


def _git_show(base_ref: str, path: str) -> str:
    """Return the text of ``path`` at ``base_ref`` via ``git show``.

    Raises :class:`BaselineUnavailable` if git exits non-zero (unknown
    ref/path, shallow clone without the ref, ...) or git is unavailable, so
    callers can treat a missing baseline as *establishing* rather than crash.
    """
    try:
        out = subprocess.check_output(  # noqa: S603 - fixed argv, no shell, trusted inputs
            ["git", "show", f"{base_ref}:{path}"],  # noqa: S607 - `git` resolved from PATH by design
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise BaselineUnavailable(f"git show {base_ref}:{path} failed: {exc}") from exc
    return out.decode("utf-8", errors="replace")


def load_baseline(
    base_ref: str,
    path: str,
    *,
    kind: str,
    runner: GitRunner = _git_show,
) -> PinSet | None:
    """Return the baseline ``{(name, version)}`` set, or ``None``.

    ``None`` means the lockfile does not exist at ``base_ref`` (the runner
    raised :class:`BaselineUnavailable`) -> the run is *baseline-establishing*.
    A present-but-unparseable lock yields an **empty set** (distinct from
    ``None``): the lock existed at the base ref so every current pin still
    counts as "added" and is a candidate for the age check.
    """
    try:
        content = runner(base_ref, path)
    except BaselineUnavailable:
        return None
    if kind == "uv":
        return {(name, version) for name, version, _ in parse_uv_lock(content)}
    try:
        obj = json.loads(content)
    except ValueError:
        return set()
    if not isinstance(obj, dict):
        return set()
    return set(parse_npm_lock(obj))


# ---------------------------------------------------------------------------
# npm registry lookup
# ---------------------------------------------------------------------------


def npm_published_at(
    name: str,
    version: str,
    *,
    opener: Opener = urllib.request.urlopen,
    timeout: float = 10,
) -> datetime | None:
    """Publish time of ``name@version`` from the npm registry, or ``None``.

    ``None`` is returned on *any* network/HTTP/JSON error or if the version
    is absent from the registry's ``time`` map; the caller decides policy
    (the guard treats it as a fail-open warning, never a silent pass).
    """
    url = f"{NPM_REGISTRY}/{urllib.parse.quote(name, safe='@')}"
    try:
        with opener(url, timeout=timeout) as resp:
            payload = json.loads(resp.read())
        times = payload["time"]
        return iso_to_dt(times[version])
    except (
        urllib.error.URLError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return None


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def find_violations(
    uv_pkgs: Iterable[UvPackage],
    npm_pkgs: Iterable[NpmPackage],
    *,
    now: datetime,
    min_age: timedelta,
    npm_published_at: NpmFetcher = npm_published_at,
    uv_baseline: PinSet | None,
    npm_baseline: PinSet | None,
) -> tuple[list[Violation], list[str], list[Violation]]:
    """Classify lock entries with delta/baseline (Dependabot-cooldown) rules.

    A pin is a *candidate* only if it is **not** in the baseline set (added or
    version-changed) -- unless the baseline is ``None`` (establishing), in
    which case every pin is grandfathered and nothing is a violation.

    Returns ``(violations, warnings, grandfathered_young)``:

    * ``violations`` -- hard failures: candidates younger than ``min_age``
      (uv from the embedded ``upload-time``; npm via the registry).
    * ``warnings`` -- npm candidates whose registry lookup failed (fail-open;
      never blocks CI on a transient/registry error).
    * ``grandfathered_young`` -- deps younger than ``min_age`` that are
      *accepted* anyway (establishing run, or unchanged from baseline with a
      known publish time) -- surfaced purely for visibility.

    uv pins without an ``upload-time`` (root/path dep) are always ignored.
    Unchanged-from-baseline npm pins are trusted without a registry lookup.
    """
    violations: list[Violation] = []
    warnings: list[str] = []
    grandfathered: list[Violation] = []

    uv_establishing = uv_baseline is None
    for name, version, uploaded in uv_pkgs:
        if uploaded is None:
            continue
        age = now - uploaded
        if age >= min_age:
            continue
        is_candidate = not uv_establishing and (name, version) not in uv_baseline
        record = Violation("uv", name, version, uploaded, age)
        if is_candidate:
            violations.append(record)
        else:
            grandfathered.append(record)

    npm_establishing = npm_baseline is None
    for name, version in npm_pkgs:
        unchanged = not npm_establishing and (name, version) in npm_baseline
        if unchanged:
            # Trusted baseline pin: no registry call, no surfacing.
            continue
        published = npm_published_at(name, version)
        if published is None:
            warnings.append(
                f"{name}=={version}: npm registry lookup failed "
                f"(age unknown -- not blocked)"
            )
            continue
        age = now - published
        if age >= min_age:
            continue
        record = Violation("npm", name, version, published, age)
        if npm_establishing:
            grandfathered.append(record)
        else:
            violations.append(record)

    return violations, warnings, grandfathered


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_uv(path: Path) -> list[UvPackage]:
    if not path.is_file():
        return []
    return parse_uv_lock(path.read_text(encoding="utf-8"))


def _load_npm(path: Path) -> list[NpmPackage]:
    if not path.is_file():
        return []
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    if not isinstance(obj, dict):
        return []
    return parse_npm_lock(obj)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_min_dependency_age",
        description=(
            "Fail if a NEWLY ADDED or version-changed locked dependency "
            "(vs --base-ref) was published less than --min-age-days ago. "
            "Rolling cooldown that uv/npm lack natively; matches Dependabot "
            "cooldown. The first PR that introduces the lockfiles is "
            "baseline-establishing and always passes."
        ),
    )
    parser.add_argument("--uv-lock", default=DEFAULT_UV_LOCK)
    parser.add_argument("--npm-lock", default=DEFAULT_NPM_LOCK)
    parser.add_argument("--min-age-days", type=int, default=MIN_AGE_DAYS)
    parser.add_argument(
        "--base-ref",
        default=DEFAULT_BASE_REF,
        help=(
            "Git ref whose lockfiles are the trusted baseline "
            f"(default {DEFAULT_BASE_REF!r}). If a lock is absent there the "
            "run is baseline-establishing and passes."
        ),
    )
    parser.add_argument(
        "--skip-npm",
        action="store_true",
        help="Offline mode: only the uv.lock check (no network).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    min_age = timedelta(days=args.min_age_days)
    now = datetime.now(timezone.utc)

    uv_pkgs = _load_uv(Path(args.uv_lock))
    uv_baseline = load_baseline(args.base_ref, args.uv_lock, kind="uv")

    npm_pkgs: list[NpmPackage] = []
    npm_baseline: PinSet | None = None
    if not args.skip_npm:
        npm_pkgs = _load_npm(Path(args.npm_lock))
        npm_baseline = load_baseline(args.base_ref, args.npm_lock, kind="npm")

    violations, warnings, grandfathered = find_violations(
        uv_pkgs,
        npm_pkgs,
        now=now,
        min_age=min_age,
        npm_published_at=npm_published_at,
        uv_baseline=uv_baseline,
        npm_baseline=npm_baseline,
    )

    for warning in warnings:
        print(f"warning: {warning}")

    uv_establishing = uv_baseline is None
    npm_establishing = (not args.skip_npm) and npm_baseline is None
    establishing = uv_establishing or npm_establishing
    if grandfathered:
        if establishing:
            print(
                f"INFO: baseline-establishing run vs {args.base_ref!r} "
                f"(no committed lock at base) -- "
                f"{len(grandfathered)} young dependenc"
                f"{'y' if len(grandfathered) == 1 else 'ies'} grandfathered "
                f"as the accepted baseline:"
            )
        else:
            print(
                f"INFO: {len(grandfathered)} young dependenc"
                f"{'y' if len(grandfathered) == 1 else 'ies'} unchanged from "
                f"{args.base_ref!r} baseline -- grandfathered:"
            )
        for record in grandfathered:
            print(f"  {record.render(min_age)}")

    if not violations:
        scope = "uv" if args.skip_npm else "uv + npm"
        mode = "establishing" if establishing else "delta vs " + args.base_ref
        print(
            f"OK: no newly added/upgraded dependency younger than "
            f"{args.min_age_days}d ({scope}; {mode}; "
            f"{len(uv_pkgs)} uv, {len(npm_pkgs)} npm checked)."
        )
        return 0

    print(
        f"FAIL: {len(violations)} newly added/upgraded dependenc"
        f"{'y' if len(violations) == 1 else 'ies'} younger than "
        f"{args.min_age_days}d (minimum dependency age vs "
        f"{args.base_ref!r}):"
    )
    for violation in violations:
        print(f"  {violation.render(min_age)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
