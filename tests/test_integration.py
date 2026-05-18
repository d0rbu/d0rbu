"""End-to-end integration tests via real subprocesses.

Console scripts are resolved with ``shutil.which`` and skipped if absent so
this file is portable; CI runs under the synced venv where all six aliases
resolve. No real network and no real package upgrade occur (the ``--update``
test uses a PATH shim).
"""

import os
import shutil
import subprocess
import sys

import pytest

from henry_castillo import __version__

ALIASES = ["henry-castillo", "d0rbu", "d0rb", "hc", "henry", "secret-string-lol"]

_FIRST_LINE = f"henry-castillo {__version__}"


def _resolve(alias: str) -> str:
    path = shutil.which(alias)
    if path is None:
        pytest.skip(f"console script {alias!r} not on PATH")
    return path


@pytest.mark.parametrize("alias", ALIASES)
def test_alias_bare_run(alias):
    exe = _resolve(alias)
    r = subprocess.run([exe], capture_output=True, text=True, check=False)  # noqa: S603
    assert r.returncode == 0
    assert r.stderr == ""
    for _title in ("About", "Projects", "Résumé", "Contact", "Substack"):
        assert _title in r.stdout
    # The update notice must never appear: stdout is not a tty under
    # subprocess capture, proving the isatty offline guard end-to-end.
    assert "A new release" not in r.stdout


@pytest.mark.parametrize("alias", ALIASES)
def test_alias_version_flag(alias):
    exe = _resolve(alias)
    r = subprocess.run(  # noqa: S603
        [exe, "--version"], capture_output=True, text=True, check=False
    )
    assert r.returncode == 0
    assert r.stdout == f"{_FIRST_LINE}\n"
    assert r.stderr == ""


def test_python_m_matches_bare_alias():
    exe = _resolve("henry-castillo")
    bare = subprocess.run([exe], capture_output=True, text=True, check=False)  # noqa: S603
    mod = subprocess.run(
        [sys.executable, "-m", "henry_castillo"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert mod.returncode == 0
    assert mod.stdout == bare.stdout
    assert mod.stderr == ""


def test_python_m_bogus_flag_exit_2():
    r = subprocess.run(
        [sys.executable, "-m", "henry_castillo", "--bogus"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2


def test_python_m_version_flag_exit_0():
    r = subprocess.run(
        [sys.executable, "-m", "henry_castillo", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert r.stdout == f"{_FIRST_LINE}\n"


def test_update_end_to_end_via_path_shim(tmp_path):
    """`--update` end-to-end without a real upgrade.

    A fake ``uv`` is placed first on PATH; it echoes its args and exits 7.
    perform_update prefers uv, so we deterministically observe rc 7 and the
    'Running: uv tool upgrade henry-castillo' line — no network, no install.
    """
    shim = tmp_path / "uv"
    shim.write_text('#!/bin/sh\necho "uv $@"\nexit 7\n')
    shim.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"

    r = subprocess.run(
        [sys.executable, "-m", "henry_castillo", "--update"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert r.returncode == 7
    assert "Running: uv tool upgrade henry-castillo" in r.stdout
