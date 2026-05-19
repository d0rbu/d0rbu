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
    assert card.profile.links.blog == ""
    urls = [p.url for p in card.projects]
    assert urls == [
        "https://github.com/d0rbu/mc-dreamer",
        "https://github.com/Algorithmic-Alignment-Lab/nano-gpt-pretrain-steer",
    ]
    assert [p.name for p in card.projects] == [
        "mc-dreamer",
        "nano-gpt-pretrain-steer",
    ]


def test_card_json_url_matches_cli_default():
    # The deployed path must match the CLI's hardcoded canonical URL.
    assert content._CARD_URL == "https://d0rbu.github.io/d0rbu/data/card.json"


def test_web_build_stages_dist(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    work = tmp_path / "web"
    shutil.copytree(_WEB, work)
    subprocess.run([node, "build.mjs"], cwd=work, check=True)  # noqa: S603
    built = json.loads((work / "dist" / "data" / "card.json").read_text("utf-8"))
    src = json.loads((_WEB / "data" / "card.json").read_text("utf-8"))
    assert built == src
    assert (work / "dist" / "index.html").is_file()
