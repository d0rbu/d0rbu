import subprocess

import henry_castillo
from henry_castillo.__main__ import main


def test_version_is_nonempty_string():
    assert isinstance(henry_castillo.__version__, str)
    assert henry_castillo.__version__


def test_main_returns_zero_and_prints_name(capsys):
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "henry-castillo" in out


def test_console_entrypoint_runs():
    result = subprocess.run(
        ["henry-castillo"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "henry-castillo" in result.stdout


def test_alias_entrypoint_runs():
    result = subprocess.run(["d0rbu"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "henry-castillo" in result.stdout
