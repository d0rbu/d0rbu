#!/usr/bin/env python3
"""Rolling minimum-dependency-age guard (uv.lock + npm package-lock.json).

Neither ``uv`` nor ``npm`` has a *rolling* minimum-release-age setting at the
lockfile layer (Dependabot's ``cooldown`` only gates *its* PRs, not arbitrary
manual/Dependabot lock bumps once merged). This script provides that missing
rolling guard: a dependency version pinned in a lock file must have been
published at least ``MIN_AGE_DAYS`` (default 7) ago.

Design notes
------------
* **Stdlib only**, and must run under Python 3.10 -- so ``tomllib`` (3.11+)
  is intentionally NOT used; ``uv.lock`` is parsed with a small, robust
  ``[[package]]``-block scanner instead of a TOML library.
* Pure, side-effect-free functions with injectable ``now`` / fetcher / IO so
  the behaviour is deterministic and unit-testable without a real network.

Policy
------
* **uv**: ``uv.lock`` records an ``upload-time`` for every registry package,
  so the age check is always positively decidable *offline*. A package newer
  than ``min_age`` is a hard **violation**. The root/editable project (no
  ``upload-time``) is skipped.
* **npm**: ``package-lock.json`` has no timestamps, so the publish time is
  fetched from the npm registry. A package positively newer than ``min_age``
  is a **violation**. If the lookup fails (network/registry/parse error) it
  is reported as a **warning**, not a violation -- a deliberate, documented
  fail-open so a flaky registry does not break CI. A *confirmed* too-fresh
  package is never silently passed.

This file lives outside the ``henry_castillo`` package on purpose, so it is
not measured by the package's 100% coverage gate.
"""

from __future__ import annotations

import argparse
import json
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

UvPackage = tuple[str, str, "datetime | None"]
NpmPackage = tuple[str, str]
Opener = Callable[..., Any]
NpmFetcher = Callable[..., "datetime | None"]


@dataclass(frozen=True)
class Violation:
    """A dependency confirmed to be younger than the minimum age."""

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
) -> tuple[list[Violation], list[str]]:
    """Classify lock entries into hard violations and (npm-only) warnings.

    * uv: ``upload_time`` present and ``now - upload_time < min_age`` -> a
      hard violation. Missing ``upload_time`` (root/path dep) is ignored.
    * npm: a positively-too-fresh package is a violation; a failed lookup is
      a fail-open warning (transient registry errors must not break CI).
    """
    violations: list[Violation] = []
    warnings: list[str] = []

    for name, version, uploaded in uv_pkgs:
        if uploaded is None:
            continue
        age = now - uploaded
        if age < min_age:
            violations.append(Violation("uv", name, version, uploaded, age))

    for name, version in npm_pkgs:
        published = npm_published_at(name, version)
        if published is None:
            warnings.append(
                f"{name}=={version}: npm registry lookup failed "
                f"(age unknown -- not blocked)"
            )
            continue
        age = now - published
        if age < min_age:
            violations.append(Violation("npm", name, version, published, age))

    return violations, warnings


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
            "Fail if any locked dependency was published less than "
            "--min-age-days ago (rolling guard uv/npm lack natively)."
        ),
    )
    parser.add_argument("--uv-lock", default=DEFAULT_UV_LOCK)
    parser.add_argument("--npm-lock", default=DEFAULT_NPM_LOCK)
    parser.add_argument("--min-age-days", type=int, default=MIN_AGE_DAYS)
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
    npm_pkgs: list[NpmPackage] = []
    if not args.skip_npm:
        npm_pkgs = _load_npm(Path(args.npm_lock))

    violations, warnings = find_violations(
        uv_pkgs,
        npm_pkgs,
        now=now,
        min_age=min_age,
        npm_published_at=npm_published_at,
    )

    for warning in warnings:
        print(f"warning: {warning}")

    if not violations:
        scope = "uv" if args.skip_npm else "uv + npm"
        print(
            f"OK: no dependency younger than {args.min_age_days}d "
            f"({scope}; {len(uv_pkgs)} uv, {len(npm_pkgs)} npm checked)."
        )
        return 0

    print(
        f"FAIL: {len(violations)} dependenc"
        f"{'y' if len(violations) == 1 else 'ies'} younger than "
        f"{args.min_age_days}d (minimum dependency age):"
    )
    for violation in violations:
        print(f"  {violation.render(min_age)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
