"""In-process smoke checks. Subprocess/end-to-end checks live in
tests/test_integration.py.
"""

import importlib.metadata

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


def test_main_returns_zero_and_prints_name(capsys):
    rc = main([])
    out, err = capsys.readouterr()
    assert rc == 0
    assert err == ""
    assert "About" in out
    assert "Projects" in out
    assert "A new release" not in out
