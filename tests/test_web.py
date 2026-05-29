import json
import shutil
import subprocess
from pathlib import Path

import pytest

from henry_castillo import content

_WEB = Path(__file__).resolve().parents[1] / "web"


def test_card_json_is_schema_valid():
    doc = json.loads((_WEB / "data" / "card.json").read_text(encoding="utf-8"))
    card = content.parse_card(doc)
    assert card.schema_version == content.SCHEMA_VERSION
    assert card.profile.name == "Henry Castillo"
    assert card.profile.handle == "d0rbu"
    assert card.profile.tagline == "Interpretability and safety researcher"
    assert card.profile.email == "henryandrecastillo@gmail.com"
    assert card.profile.links.github == "https://github.com/d0rbu"
    assert card.profile.links.blog == "https://substack.com/@d0rb"
    assert card.profile.links.twitter == "https://x.com/henrycstllo"
    urls = [p.url for p in card.projects]
    assert urls == [
        "https://github.com/d0rbu/mc-dreamer",
        "https://github.com/Algorithmic-Alignment-Lab/nano-gpt-pretrain-steer",
    ]
    assert [p.name for p in card.projects] == [
        "mc-dreamer",
        "nano-gpt-pretrain-steer",
    ]


def test_web_card_json_validates_against_schema():
    """web/data/card.json must pass jsonschema Draft 2020-12 validation."""
    doc = json.loads((_WEB / "data" / "card.json").read_text(encoding="utf-8"))
    # validate() raises ValidationError if invalid; passes silently if valid.
    content._validator().validate(doc)


def test_web_card_json_schema_version_matches_schema_const():
    """web/data/card.json schema_version must equal the schema's const value."""
    doc = json.loads((_WEB / "data" / "card.json").read_text(encoding="utf-8"))
    schema_const = content._schema()["properties"]["schema_version"]["const"]
    assert doc["schema_version"] == schema_const


def test_web_card_json_has_dollar_schema_key():
    """web/data/card.json must carry the $schema annotation."""
    doc = json.loads((_WEB / "data" / "card.json").read_text(encoding="utf-8"))
    assert "$schema" in doc
    assert doc["$schema"].endswith("card.schema.json")


def test_card_json_url_matches_cli_default():
    # The deployed path must match the CLI's hardcoded canonical URL.
    assert content._CARD_URL == "https://d0rbu.github.io/d0rbu/data/card.json"


def test_web_build_stages_dist(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    # Mirror the repo layout that build.mjs expects:
    # tmp/web/ and tmp/src/henry_castillo/
    work = tmp_path / "web"
    shutil.copytree(_WEB, work)
    # build.mjs resolves schema via resolve(__dirname, "..", "src", ...) so we
    # must place the schema at the same relative location in the tmp tree.
    schema_src = _WEB.parents[0] / "src" / "henry_castillo" / "card.schema.json"
    schema_dst_dir = tmp_path / "src" / "henry_castillo"
    schema_dst_dir.mkdir(parents=True)
    shutil.copy2(schema_src, schema_dst_dir / "card.schema.json")
    subprocess.run([node, "build.mjs"], cwd=work, check=True)  # noqa: S603
    built = json.loads((work / "dist" / "data" / "card.json").read_text("utf-8"))
    src = json.loads((_WEB / "data" / "card.json").read_text("utf-8"))
    assert built == src
    assert (work / "dist" / "index.html").is_file()
    assert (work / "dist" / "data" / "card.schema.json").is_file()
