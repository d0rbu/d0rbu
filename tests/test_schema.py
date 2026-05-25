"""Tests for the bundled card.schema.json artifact."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from henry_castillo import content

_SCHEMA_FILE = (
    Path(__file__).resolve().parents[1] / "src" / "henry_castillo" / "card.schema.json"
)


def test_schema_is_valid_draft_2020_12():
    """The schema must itself be a valid Draft 2020-12 schema."""
    schema = json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))
    # Raises if invalid; implicitly passes if not.
    jsonschema.Draft202012Validator.check_schema(schema)


def test_additional_properties_false_at_every_object_level():
    """additionalProperties must be false at every object in the schema."""
    schema = json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))

    # Collect all object-level sub-schemas that must have additionalProperties: false.
    checks = [
        ("root", schema),
        ("profile", schema["properties"]["profile"]),
        ("profile.links", schema["properties"]["profile"]["properties"]["links"]),
        ("projects.items", schema["properties"]["projects"]["items"]),
        ("resume", schema["properties"]["resume"]),
        ("demos.items", schema["properties"]["demos"]["items"]),
    ]
    for path, sub in checks:
        assert sub.get("additionalProperties") is False, (
            f"additionalProperties is not false at {path!r}"
        )


def test_schema_importable_from_package_at_runtime():
    """content._schema() must return the same dict as the on-disk file."""
    # Clear the lru_cache so we get a fresh load in this test environment.
    content._schema.cache_clear()
    content._validator.cache_clear()

    runtime_schema = content._schema()
    assert isinstance(runtime_schema, dict)
    assert runtime_schema.get("$id", "").endswith("card.schema.json")

    disk_schema = json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))
    assert runtime_schema == disk_schema


def test_schema_id_and_title():
    """Spot-check key metadata in the schema."""
    schema = content._schema()
    assert schema["$id"] == "https://d0rbu.github.io/d0rbu/data/card.schema.json"
    assert schema["title"] == "henry-castillo card"
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_version_const_is_2():
    """schema_version must be constrained to exactly 2."""
    schema = content._schema()
    assert schema["properties"]["schema_version"] == {"const": 2}


@pytest.mark.parametrize(
    "path,key",
    [
        ("profile.name", ("properties", "profile", "properties", "name")),
        ("profile.handle", ("properties", "profile", "properties", "handle")),
        ("profile.tagline", ("properties", "profile", "properties", "tagline")),
        ("profile.about", ("properties", "profile", "properties", "about")),
        ("profile.email", ("properties", "profile", "properties", "email")),
        (
            "profile.links.github",
            (
                "properties",
                "profile",
                "properties",
                "links",
                "properties",
                "github",
            ),
        ),
        (
            "projects.items.name",
            ("properties", "projects", "items", "properties", "name"),
        ),
        (
            "projects.items.url",
            ("properties", "projects", "items", "properties", "url"),
        ),
        ("demos.items.name", ("properties", "demos", "items", "properties", "name")),
        (
            "demos.items.summary",
            ("properties", "demos", "items", "properties", "summary"),
        ),
        (
            "demos.items.min_version",
            ("properties", "demos", "items", "properties", "min_version"),
        ),
    ],
)
def test_required_string_fields_have_minlength_1(path, key):
    """All _req fields in the parser must have minLength: 1 in the schema."""
    schema = content._schema()
    node = schema
    for k in key:
        node = node[k]
    assert node.get("minLength") == 1, f"{path!r} must have minLength: 1"


@pytest.mark.parametrize(
    "path,key",
    [
        (
            "profile.links.blog",
            (
                "properties",
                "profile",
                "properties",
                "links",
                "properties",
                "blog",
            ),
        ),
        (
            "projects.items.blurb",
            ("properties", "projects", "items", "properties", "blurb"),
        ),
        ("resume.pdf", ("properties", "resume", "properties", "pdf")),
    ],
)
def test_optional_string_fields_have_no_minlength(path, key):
    """_opt fields must NOT have minLength: 1 (they allow empty strings)."""
    schema = content._schema()
    node = schema
    for k in key:
        node = node[k]
    assert "minLength" not in node, f"{path!r} must not have minLength"
    assert node.get("type") == "string", f"{path!r} must be type: string"


def test_projects_has_min_items_1():
    """projects array must have minItems: 1 (matching parser's non-empty check)."""
    schema = content._schema()
    assert schema["properties"]["projects"]["minItems"] == 1


def test_demos_has_no_min_items():
    """demos array must NOT have minItems (empty list is valid)."""
    schema = content._schema()
    assert "minItems" not in schema["properties"]["demos"]
