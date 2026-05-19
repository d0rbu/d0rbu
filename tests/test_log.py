import importlib

from henry_castillo import _log


def test_logger_silent_by_default(capsys):
    _log.configure(debug=False)
    _log.logger.error("should-not-appear")
    captured = capsys.readouterr()
    assert "should-not-appear" not in captured.err
    assert "should-not-appear" not in captured.out


def test_logger_emits_on_debug(capsys):
    _log.configure(debug=True)
    try:
        _log.logger.error("diag-msg-xyz")
        captured = capsys.readouterr()
        assert "diag-msg-xyz" in captured.err
    finally:
        _log.configure(debug=False)  # restore global state


def test_configure_idempotent_toggle(capsys):
    _log.configure(debug=True)
    _log.configure(debug=True)  # second enable must not double-sink
    _log.configure(debug=False)
    _log.configure(debug=False)  # second disable must be a no-op
    _log.logger.error("none-xyz")
    assert "none-xyz" not in capsys.readouterr().err


def test_debug_enabled_cli_flag_wins():
    assert _log.debug_enabled(cli_flag=True) is True


def test_debug_enabled_env(monkeypatch):
    monkeypatch.delenv("HENRY_CASTILLO_DEBUG", raising=False)
    assert _log.debug_enabled(cli_flag=False) is False
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "1")
    assert _log.debug_enabled(cli_flag=False) is True
    monkeypatch.setenv("HENRY_CASTILLO_DEBUG", "true")
    assert _log.debug_enabled(cli_flag=False) is True
    for falsey in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("HENRY_CASTILLO_DEBUG", falsey)
        assert _log.debug_enabled(cli_flag=False) is False


def test_module_import_is_silent(capsys):
    importlib.reload(_log)
    _log.logger.info("import-noise-xyz")
    out = capsys.readouterr()
    assert "import-noise-xyz" not in out.err and "import-noise-xyz" not in out.out
    _log.configure(debug=False)  # leave global state clean
