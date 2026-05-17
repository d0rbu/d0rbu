"""Update checking and best-effort self-update for the henry-castillo CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from packaging.version import InvalidVersion, Version

PACKAGE = "henry-castillo"
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE}/json"
CHECK_INTERVAL_SECONDS = 60 * 60 * 24


def current_version() -> str:
    """Installed distribution version, falling back to the package attribute."""
    try:
        return version(PACKAGE)
    except PackageNotFoundError:
        from henry_castillo import __version__  # noqa: PLC0415

        return __version__


def cache_path() -> Path:
    """Per-user cache file for the throttled update check."""
    base = os.environ.get("XDG_CACHE_HOME")
    if not base or not Path(base).is_absolute():
        base = str(Path.home() / ".cache")
    return Path(base) / "henry-castillo" / "update-check.json"


def fetch_latest_version(timeout: float = 2.0, *, url: str = PYPI_URL) -> str | None:
    """Return the latest version string from PyPI, or None on any failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            data = json.load(resp)
        v = data["info"]["version"]
        if not isinstance(v, str):
            return None
        return v
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None


def is_outdated(current: str, latest: str) -> bool:
    """True if `latest` is a strictly newer version than `current`."""
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


def _read_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    except OSError:
        pass


def check_for_update(
    *,
    now: float | None = None,
    cache_path: Path | None = None,
    interval: int = CHECK_INTERVAL_SECONDS,
    fetcher=fetch_latest_version,
) -> str | None:
    """Return the newer version string if one exists, else None.

    Throttled to at most once per `interval` seconds via an on-disk cache so
    normal CLI runs never pay a network round-trip more than daily.
    """
    now = time.time() if now is None else now
    path = cache_path if cache_path is not None else globals()["cache_path"]()
    cache = _read_cache(path)
    latest = cache.get("latest")
    last = cache.get("last_check", 0)
    if now - last >= interval:
        fetched = fetcher()
        if fetched is not None:
            latest = fetched
        # Advance the throttle even on a failed fetch so an offline machine
        # does not pay the network timeout on every run; preserve any
        # previously cached `latest`.
        _write_cache(path, {"last_check": now, "latest": latest})
    if latest and is_outdated(current_version(), latest):
        return latest
    return None


def update_notice(latest: str) -> str:
    """Human-facing one-liner shown when a newer release exists."""
    return (
        f"A new release of henry-castillo is available: "
        f"{current_version()} -> {latest}. "
        f"Run `henry-castillo --update` to upgrade."
    )


def perform_update() -> int:
    """Best-effort self-upgrade. Returns the upgrade process exit code."""
    if shutil.which("uv"):
        cmd = ["uv", "tool", "upgrade", PACKAGE]
    elif shutil.which("pipx"):
        cmd = ["pipx", "upgrade", PACKAGE]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE]
    print("Running:", " ".join(cmd))
    try:
        return subprocess.call(cmd)  # noqa: S603
    except OSError as exc:
        print(f"Update failed: {exc}")
        return 1
