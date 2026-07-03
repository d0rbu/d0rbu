"""Tests that .pre-commit-config.yaml contains the check-jsonschema enforcement layer.

No YAML dependency — plain substring checks on the raw file text.
"""

from __future__ import annotations

from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parents[1] / ".pre-commit-config.yaml"


def test_check_jsonschema_hook_id_present() -> None:
    """The config must reference the check-jsonschema hook id."""
    text = _CONFIG_FILE.read_text(encoding="utf-8")
    assert "check-jsonschema" in text


def test_check_jsonschema_schemafile_arg_present() -> None:
    """The hook must pass the local card.schema.json as --schemafile."""
    text = _CONFIG_FILE.read_text(encoding="utf-8")
    assert "--schemafile" in text
    assert "src/henry_castillo/card.schema.json" in text


def test_check_jsonschema_files_pattern_present() -> None:
    """The hook must target exactly web/data/card.json via files pattern."""
    text = _CONFIG_FILE.read_text(encoding="utf-8")
    assert r"^web/data/card\.json$" in text
