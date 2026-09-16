# Schema-Hardened `card.json` + Demo-Aware Update Indicator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Plan + spec kept UNTRACKED (never `git add`ed). Additional commits on `milestone-2-cli` / PR #3 (NOT merged). Gate after every task: exactly 100% line+branch, zero `# pragma: no cover` in `src/`, ruff/ruff-format/ty/pre-commit(all hooks)/`uv lock --locked`/dependency-age(`--skip-npm`)/`make check`, Python 3.10-safe. Conventional commits + `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.

**Goal:** Make `card.json` provably conform to a strict JSON Schema (enforced at commit, CI, deploy, and runtime) and make the Demos menu entry name the demos a newer release would add.

**Architecture:** Single canonical `web/data/card.schema.json` (Draft 2020-12, `additionalProperties:false` everywhere). The runtime fetch→validate(jsonschema)→strict-parse→sanitize pipeline gains a schema gate; the typed parser is tightened to reject unknown keys so it matches the schema; a Hypothesis drift test binds the two. A required `demos[]` field (schema_version→2) feeds a `new_demos` helper; the TUI Demos entry shows a named badge iff a newer release exists AND it adds demos.

**Tech stack:** Python (uv/ruff/ty/pytest), `jsonschema` (new pinned runtime dep), `packaging` (already a dep — reused for version compare), `check-jsonschema` (new pinned pre-commit hook), rich, hatchling force-include, Node zero-dep `web/build.mjs`.

Baseline: `milestone-2-cli` @ `4271ca4`, `git status` = only untracked `docs/`.

---

### Task 1: `demos` model + `schema_version`→2 + strict parser tightening + fixtures

**Files:**
- Modify: `src/henry_castillo/content.py`
- Modify: `web/data/card.json`
- Modify: `tests/conftest.py`, `tests/test_card.py`, `tests/test_cli.py`, `tests/test_render.py`, `tests/test_tui.py`, `tests/test_property.py`, `tests/test_web.py`

**Changes (`content.py`):**
- Add `from packaging.version import InvalidVersion, Version` to imports.
- `SCHEMA_VERSION = 1` → `= 2` (line 68).
- New frozen dataclass after `Project`:
  ```python
  @dataclass(frozen=True)
  class Demo:
      name: str
      summary: str
      min_version: str
  ```
- `Card` gains `demos: list[Demo]` (after `resume`).
- `_CARD_REQUIRED_KEYS` add `"demos"`. Define `_CARD_ALLOWED_KEYS = _CARD_REQUIRED_KEYS | {"$schema"}`.
- New `_parse_demo(it: object, i: int) -> Demo`: require dict; reject unknown keys (allowed = `{"name","summary","min_version"}`); `name`/`summary` via `_req` (non-empty); `min_version` via `_req` then `Version(min_version)` guarded by `except InvalidVersion: raise CardError(f"demos[{i}].min_version: not a valid version")`; sanitize all three strings (they flow through `_sanitize` like other content — confirm `_req`/parse path sanitizes; if not, sanitize explicitly to match `Project`).
- In `parse_card`: after the required-subset check, add an **unknown-key rejection** at root: `extra = set(dd.keys()) - _CARD_ALLOWED_KEYS; if extra: raise CardError(f"card: unexpected key(s): {sorted(extra)}")`. Parse `demos`: `raw_demos = dd.get("demos"); if not isinstance(raw_demos, list): raise CardError("demos: expected a list")` (empty list allowed) → `demos=[_parse_demo(it, i) for i, it in enumerate(raw_demos)]`. Pass `demos=` to `Card(...)`.
- **Tighten the nested parse helpers to reject unknown keys** (to match the schema's `additionalProperties:false` at every level — required for the drift iff in Task 2): in `_parse_profile` (allowed = `{"name","handle","tagline","about","email","links"}`), the `links` object (`{"github","blog"}`), `_parse_project` (`{"name","blurb","url","tags"}`), `_parse_resume` (`{"pdf","experience","education","highlights"}`). Each: `extra = set(d.keys()) - allowed; if extra: raise CardError(f"<path>: unexpected key(s): {sorted(extra)}")`. Keep messages path-named.
- New pure helper for the badge (used in Task 4), with its own tests here:
  ```python
  def new_demos(card: Card, *, current: str) -> list[Demo]:
      """Demos whose min_version is strictly greater than `current`."""
      cur = Version(current)
      return [d for d in card.demos if Version(d.min_version) > cur]
  ```
  (`current` comes from `update.current_version()`; demos' `min_version` already validated parseable at parse time, so no guard needed here. `current` from `current_version()` is always valid.)

**Changes (`web/data/card.json`):** bump `"schema_version": 2`, add `"demos": []`. (The `"$schema"` annotation is added in Task 2 with the schema file.)

**Changes (tests) — keep the suite green at 100%:**
- `conftest.py:_VALID_CARD_DOC` → `schema_version: 2`, add `"demos": []`.
- `test_card.py`: `_VALID` → `schema_version: 2` + `"demos": []`; `:62` assertion `== 1` → `== 2`; the `schema_version` parametrize (`:90`) — `2` is now VALID so remove it from the invalid set and add an explicit valid-`2`/invalid-`1` pair (`1` now → CardError, `2` → ok); add demos tests: valid demos parse to `Demo`s; each of missing/empty `name`/`summary`, missing/empty/`InvalidVersion` `min_version`, non-list `demos`, extra key in a demo → `CardError` with the right path; unknown root key → CardError; unknown key in profile/links/project/resume → CardError; `$schema` extra root key → accepted+ignored.
- `test_cli.py`, `test_render.py`, `test_tui.py`: each `_VALID_DOC` → `schema_version: 2` + `"demos": []`.
- `test_property.py`: the card strategy (`:38`) must now also generate a `demos` list (a strategy producing 0..n `{name,summary,min_version}` with non-empty strings + valid version strings) so generated docs parse; `st.just(content.SCHEMA_VERSION)` already auto-tracks the bump.
- `test_web.py`: passes once `web/data/card.json` has `demos` + v2 (`:16` uses the constant, auto-tracks).
- Add `new_demos` unit tests: equal version → not new; lower → not new; higher → new; pre/rc/post-release ordering; multiple demos mixed; empty demos → [].

**Steps:** (1) write the new/changed tests (red); (2) implement `content.py` + `web/data/card.json`; (3) update all fixtures/docs; (4) `uv run pytest` green + 100%; (5) full gate; (6) commit `feat: add strict demos manifest and tighten card schema_version to 2`.

---

### Task 2: JSON Schema artifact + runtime validation + bundling + drift test

**Files:**
- Create: `web/data/card.schema.json`
- Modify: `web/data/card.json` (add `"$schema"`), `web/build.mjs` (stage schema), `src/henry_castillo/content.py` (runtime validation + schema loader), `pyproject.toml` (add `jsonschema` dep + force-include), `uv.lock` (regen)
- Test: `tests/test_card.py` (runtime-gate cases), `tests/test_property.py` (drift), `tests/test_web.py` (schema validity + real-card validates), new `tests/test_schema.py` (artifact + packaged-bytes equality)

**Schema (`web/data/card.schema.json`)** — Draft 2020-12, `$id: https://d0rbu.github.io/d0rbu/data/card.schema.json`, `additionalProperties:false` at every object level, `required` lists all fields, `schema_version` `const: 2`, content strings `minLength:1` (matching `_req`), optional strings (`projects[].blurb`, `links.blog`, `resume.pdf`) `type:string` only (matching `_opt`), `projects` `minItems:1`, `demos` array (empty allowed) of `{name:minLength1, summary:minLength1, min_version:string+minLength1}` (NO `pattern` — version semantics are the runtime parser's job; see drift note), `resume.experience`/`education` arrays of objects, `highlights` array of strings, root `"$schema": {"type":"string"}` allowed-not-required.

**Runtime (`content.py`):**
- Add `import jsonschema` (and `import importlib.resources`).
- `_schema() -> dict`: read packaged `card.schema.json` via `importlib.resources.files("henry_castillo").joinpath("card.schema.json").read_text("utf-8")` → `json.loads`; wrap in `functools.lru_cache` (read once). No try/except — OSError/ValueError from a (build-broken) schema propagate into `load_card`'s existing `(OSError, ValueError, …)` catch → graceful cache/failure path (no new uncovered branch).
- `_validator()` (lru_cache): `jsonschema.Draft202012Validator(_schema())`.
- `_validate_schema(doc: object) -> None`: `try: _validator().validate(doc) except jsonschema.exceptions.ValidationError as e: _log.logger.error("card.json failed schema validation: {}", e.message); raise CardError(f"card.json does not match the expected schema: {'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}") from e`.
- `_parse_bytes`: `doc = json.loads(raw.decode("utf-8")); _validate_schema(doc); return parse_card(doc)`. (`_validate_schema` emits only `CardError`; `load_card`'s catch tuple is unchanged.)
- Import `_log` if not already (for the error log).

**`pyproject.toml`:** add `"jsonschema==<latest version ≥7 days old as of 2026-05-24>"` to `[project.dependencies]` (pick via `uv add`, then verify); add force-include `"web/data/card.schema.json" = "henry_castillo/card.schema.json"`. Run `uv lock`. **Dependency-age:** run `uv run python scripts/check_min_dependency_age.py --skip-npm`; if any newly-locked transitive pin (`referencing`, `rpds-py`, `attrs`, `jsonschema-specifications`) is <7 days old, re-resolve older (`uv lock --exclude-newer 2026-05-17`) or constrain until the guard passes.

**`web/build.mjs`:** after the `card.json` `cpSync`, add `cpSync(resolve(__dirname,"data","card.schema.json"), resolve(dist,"data","card.schema.json"))`.

**`web/data/card.json`:** add `"$schema": "https://d0rbu.github.io/d0rbu/data/card.schema.json"` as the first key.

**Tests:**
- `tests/test_schema.py` (new): the schema is a valid Draft 2020-12 schema (`Draft202012Validator.check_schema(schema)`); `additionalProperties:false` present at every object level (structural assertions); the **packaged** `card.schema.json` bytes (`importlib.resources`) equal `web/data/card.schema.json` bytes (no drift between shipped & deployed).
- `tests/test_web.py`: real `web/data/card.json` validates against the schema; its `schema_version` is the schema's `const`.
- `tests/test_card.py`: a JSON-valid but schema-invalid fetched body (e.g. stray key, missing `demos`, wrong type) → `load_card` raises `CardError` (runtime gate) and logs at error; a schema-valid body proceeds.
- `tests/test_property.py` **drift property:** strategy generating card-shaped docs (valid + structurally-invalid variants: missing/extra keys, wrong types, empty required strings; `min_version` drawn from VALID version strings so it is never the differentiator) → assert `is_valid := not list(_validator().iter_errors(doc))` equals `parse_card`-succeeds (`try parse_card(doc); ok=True except CardError: ok=False`); the two MUST agree. (Min_version-semantics invalidity is covered by the Task 1 unit test, explicitly outside this property.)

**Steps:** TDD red→green per file; full gate (incl. dependency-age, `uv lock --locked`, twine/build still fine since the wheel now ships the schema); commit `feat: validate card.json against a bundled JSON Schema at load time`.

---

### Task 3: `check-jsonschema` pre-commit hook (author + CI enforcement)

**Files:** Modify `.pre-commit-config.yaml`; Test: `tests/test_schema.py` (hook config assertion) — and a manual/scripted rejection check.

**Changes:** add an external, tag-pinned hook (matching the repo's existing tag-pinned style):
```yaml
  - repo: https://github.com/python-jsonschema/check-jsonschema
    rev: <tag ≥7 days old as of 2026-05-24>
    hooks:
      - id: check-jsonschema
        name: card.json matches card.schema.json
        files: ^web/data/card\.json$
        args: ["--schemafile", "web/data/card.schema.json"]
```
The CI `quality` job already runs `pre-commit run --all-files --show-diff-on-failure`, so this is enforced on every PR with no new CI job.

**Tests / verification:** a test asserting the hook entry exists in `.pre-commit-config.yaml` (parse YAML; assert a `check-jsonschema` hook with the right `files`/`args` targeting the schema) so the enforcement layer can't be silently dropped. Then **demonstrate rejection**: run `pre-commit run check-jsonschema --files <a temp broken card>` (stray key / missing demos) and confirm non-zero exit; restore. Confirm `pre-commit run --all-files` is fully green on the real tree.

**Steps:** add hook; `pre-commit autoupdate`-free (pin manually); verify green on real card + red on a broken card; full gate; commit `build: enforce card.json against its JSON Schema via pre-commit (and CI)`.

---

### Task 4: Demo-aware Demos badge (named, both-signals)

**Files:** Modify `src/henry_castillo/tui.py`, `src/henry_castillo/__main__.py`; Test: `tests/test_tui.py`, `tests/test_cli.py`.

**Changes:**
- `tui.run` signature gains `new_demos: list[Demo] = ()` (import `Demo`/use `content.Demo`; default empty tuple, annotate `Sequence[Demo]`). In the `_DEMOS` branch, replace the current generic badge:
  ```python
  if choice == _DEMOS:
      console.print(Text("Demos are under construction…"))
      if update_available and new_demos:
          console.print(Text("New demos in a newer henry-castillo — run `henry-castillo --update`:"))
          for d in new_demos:
              console.print(Text(f"● {d.name} — {d.summary}"))
      continue
  ```
  (Text-everywhere; names/summaries already sanitized at parse. The plain generic "a newer … is available" line is removed from the Demos branch — the general startup notice still covers a plain version bump.)
- `__main__.main` (interactive TTY path): compute `new = content.new_demos(card, current=_update.current_version()) if (latest is not None) else []` (only meaningful when a newer release exists; cheap) and pass `new_demos=new` to `tui.run(...)`. Keep `update_available=latest is not None`.

**Tests:**
- `tui` 4-cell truth table via the injected `select`/`console` capture: (update_available ∈ {F,T}) × (new_demos ∈ {[], [d1,d2]}) → the named lines appear in EXACTLY the (T, non-empty) cell, listing each `name — summary`; plain "under construction" with NO badge otherwise. Markup-safety: a demo whose `name`/`summary` contains `[red]`/control chars renders literally / stripped (build the demo via `parse_card` so sanitize applies).
- `cli`/`__main__`: with a stubbed `check_for_update` returning a version AND a card whose demos include one with `min_version` > installed, the interactive run receives a non-empty `new_demos` (assert via a `tui.run` spy capturing kwargs); with `check_for_update`→None, `new_demos` is passed `[]`. Preserve all existing update-badge/notice tests (the general notice path is unchanged).

**Steps:** TDD red→green; full gate; commit `feat: name the demos a newer release adds in the Demos menu`.

---

## After all tasks
Final whole-implementation review (independent, read-only): net diff vs `4271ca4` coherent + conventional + trailered; spec §1–§11 honored; genuine 100% zero-pragma; all CI green; schema enforced at all 4 layers + drift test binds schema↔parser; demos badge both-signals+named; main untouched; plan/spec untracked; PR #3 Ready, NOT merged. Then push, watch all CI checks green, then real-data/API smoke (clean-venv wheel ships the schema; runtime validates the real card; a tampered served card → #6 screen; pre-commit rejects a broken card; a stubbed newer-release-with-new-demo → named badge). Report to the user.

## Self-review notes
- Coverage: every new branch (demo parse errors, unknown-key rejections at each level, schema ValidationError path, `new_demos` comparison) needs a hitting test — enumerated above. The schema-loader has no try/except (errors ride the existing `load_card` catch), avoiding an uncoverable branch.
- Drift iff holds because parse_card now rejects unknown keys at every level (matches `additionalProperties:false`) and the strategy uses valid `min_version`s (the one semantic check JSON Schema can't mirror exactly).
- No new runtime dep beyond `jsonschema` (`packaging` already present); pre-commit hook + jsonschema both pinned ≥7-day-old.
- Type consistency: `Demo(name,summary,min_version)`, `Card.demos: list[Demo]`, `new_demos(card,*,current)->list[Demo]`, `tui.run(..., new_demos: Sequence[Demo]=())` used consistently across tasks.
