"""In-process smoke checks. Subprocess/end-to-end checks live in
tests/test_integration.py.
"""

import importlib.metadata
import os
import subprocess
import sys
import tempfile

from packaging.version import Version

import henry_castillo
from henry_castillo.__main__ import main


def test_version_is_nonempty_string():
    assert isinstance(henry_castillo.__version__, str)
    assert henry_castillo.__version__


def test_version_matches_distribution_metadata():
    assert henry_castillo.__version__ == importlib.metadata.version("henry-castillo")


def test_version_is_pep440_parseable():
    assert str(Version(henry_castillo.__version__)) == henry_castillo.__version__


def test_main_returns_zero_and_renders_card(capsys):
    rc = main([])
    out, err = capsys.readouterr()
    assert rc == 0
    assert err == ""
    for _title in ("About", "Projects", "Résumé", "Contact", "Blog"):
        assert _title in out
    assert "A new release" not in out


def test_non_tty_no_card_failure_path():
    """#6: non-tty subprocess with unreachable URL and empty cache → rc==1,
    friendly message + contact email on stderr, no traceback, nothing opened.
    """
    with tempfile.TemporaryDirectory() as empty_cache:
        env_patch = {
            "HENRY_CASTILLO_CARD_URL": "http://127.0.0.1:1/card.json",
            "XDG_CACHE_HOME": empty_cache,
            "HENRY_CASTILLO_NO_UPDATE_CHECK": "1",
        }
        env = {**os.environ, **env_patch}
        r = subprocess.run(
            [sys.executable, "-m", "henry_castillo"],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.PIPE,  # non-tty stdin
            env=env,
        )
    assert r.returncode == 1, f"Expected rc=1, got {r.returncode}"
    assert "no usable profile data" in r.stderr.lower(), (
        f"Expected failure message on stderr, got: {r.stderr!r}"
    )
    assert "henryandrecastillo@gmail.com" in r.stderr
    assert "Traceback" not in r.stderr
