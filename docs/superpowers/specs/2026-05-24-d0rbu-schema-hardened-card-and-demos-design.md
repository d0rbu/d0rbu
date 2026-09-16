# d0rbu — Schema-Hardened `card.json` + Demo-Aware Update Indicator

**Status:** Approved 2026-05-24. Builds on
`2026-05-19-d0rbu-content-rearchitecture-design.md` (remote `card.json`, strict
no-default model, cache, guided failure). Adds (a) a demo manifest + a
demo-aware Demos badge, and (b) a formal JSON Schema as the canonical contract
for `card.json`, enforced at author, CI, deploy, **and runtime** time. Lands as
additional commits on **PR #3** (still unmerged — the maintainer reviews &
merges). Spec + plan are kept **untracked** (process artifacts stay out of the
repo/PR, per the maintainer's standing rule).

## 1. Goals

1. The Demos menu entry should advertise an update **only when a newer release
   actually adds demos the user does not have yet**, and should **name** those
   demos (so the user knows what they would get). A plain newer release with no
   new demos is surfaced only by the existing general startup notice.
2. `card.json` must provably **adhere to a strict schema**: a formal JSON Schema
   is the canonical contract, and a non-conforming file is *structurally unable*
   to be committed, merged, deployed, or consumed. This is defense-in-depth on
   top of the existing strict typed parser, not a replacement for it.

## 2. Data contract — `card.json` `schema_version` 1 → 2

One new required top-level field `demos` (a list, possibly empty):

```jsonc
{
  "$schema": "https://d0rbu.github.io/d0rbu/data/card.schema.json", // annotation; ignored by the parser
  "schema_version": 2,
  "profile": { … as in the prior spec … },
  "projects": [ … ],
  "resume":   { … },
  "demos": [
    { "name": "…", "summary": "one line: what it is", "min_version": "0.2.0" }
  ]
}
```

- `demos[i]`: `name` (non-empty string), `summary` (non-empty one-line string),
  `min_version` (PEP 440 version string — the package version this demo first
  ships in). `demos` may be `[]` (the explicit "no demos yet" — `lab`/demos is a
  deferred stub; the deployed card ships `[]`).
- `schema_version` is now **`2`** (the schema pins it via `const: 2`; the runtime
  pins it too). Nothing is published, so no migration/back-compat is needed; a
  schema-1 document is rejected.
- `card.json` carries a top-level `"$schema"` string pointing at the deployed
  schema so editors live-validate while the maintainer hand-edits. It is an
  allowed-but-optional annotation key in the schema and is **ignored** by the
  typed parser (it is metadata, not content).

## 3. Canonical contract artifact — `web/data/card.schema.json`

A single JSON Schema (Draft 2020-12) document is the source of truth for the
*shape* of `card.json`:

- `additionalProperties: false` at **every** object level (root, `profile`,
  `links`, each `project`, each `demo`, `resume`) — a stray or typo'd key is
  **rejected**, not silently ignored. (`$schema` is the one explicitly-allowed
  optional root annotation.)
- `required` lists every field; strings that must carry content use
  `minLength: 1`; `schema_version` is `const: 2`; `min_version` uses a
  conservative PEP 440-ish `pattern`; `projects`/`demos` are typed arrays with
  fully-specified item schemas; `resume.experience`/`education` are arrays of
  objects, `highlights` an array of strings.
- The schema has a stable `$id` (the deployed URL) and declares its meta-schema
  (`$schema: https://json-schema.org/draft/2020-12/schema`).

This file lives once at `src/henry_castillo/card.schema.json` — the single
canonical copy. It is importable at runtime via `importlib.resources` in both
an editable/dev install and the built wheel, deployed to Pages by `build.mjs`
(staged into `dist/data/card.schema.json` so the `$schema` URL and any external
consumer resolve it), and force-included into the wheel (§6). No second copy /
no byte-sync test is needed because there is exactly one file.

## 4. Strict typed model additions

- New frozen, no-default dataclass `Demo(name: str, summary: str, min_version: str)`.
- `Card` gains `demos: list[Demo]` (mirrors the existing `projects: list[Project]`).
- `SCHEMA_VERSION` constant becomes `2`.
- `parse_card` parses `demos` strictly, exactly like `projects`: `demos` must be
  a list; each item a dict with exactly the required keys and correct types;
  empty/missing strings, bad `min_version`, non-list, or extra keys →
  `CardError` naming the path (e.g. `demos[1].min_version`). The `$schema`
  annotation key, if present, is accepted and ignored (it is not stored on
  `Card`). Every demo string is sanitized (§5 of the prior spec) like all other
  content strings.

## 5. Loading & validation pipeline (runtime layer 4)

`load_card()` gains a schema-validation gate **before** the typed parse:

1. Fetch bytes (unchanged: HTTPS, timeout, body cap, injected seam).
2. `json.loads` the bytes (failure → `CardError`).
3. **Validate the decoded document against the packaged JSON Schema** using
   `jsonschema` (the reference implementation). A validation error → `CardError`
   whose message names the failing path; the full validator message is emitted
   via `logger.error` for the maintainer/`--debug`, never shown raw to the user.
4. `parse_card` the (now schema-valid) document into the sanitized typed `Card`.
5. Cache / cache-fallback / no-usable-data → `CardError` behavior is unchanged
   from the prior spec (the schema gate applies equally to the fetched body and
   to a cached body before it is trusted).

The schema is loaded from the package via `importlib.resources`
(`henry_castillo/card.schema.json`), parsed once, and reused. Loading/validation
raises only `CardError` to callers (the existing broad-but-typed catch set is
extended to include `jsonschema`'s exception types, normalized to `CardError`).

## 6. Dependencies & bundling (consequences of "validate at runtime")

- **New pinned runtime dependency**: `jsonschema` (exact `==`, ≥7 days old at add
  time, in `[project.dependencies]`, covered by the dependency-age guard like
  `loguru`). Deliberately the *same engine* used by `check-jsonschema` at author/
  CI time, so all gates validate with identical semantics. Its transitive tree
  (`referencing`, `rpds-py`, `attrs`, `jsonschema-specifications`) enters via
  `uv.lock`; this is the accepted cost of runtime validation.
- **One file bundled into the wheel**: `src/henry_castillo/card.schema.json` —
  the *contract* (versioned with the code), not *content* (which stays remote).
  A minimal `[tool.hatch.build.targets.wheel.force-include]` maps
  `src/henry_castillo/card.schema.json` → `henry_castillo/card.schema.json`
  (mirroring the existing `py.typed` entry). This is a deliberate, scoped
  reversal of the prior spec's "nothing bundled" — justified because a schema is
  code-contract. Runtime reads it via `importlib.resources.files`.
- **New pinned dev/CI tool**: `check-jsonschema` as a pinned pre-commit hook
  (rev pinned to a ≥7-day-old release), validating `web/data/card.json` against
  `web/data/card.schema.json`.
- `jsonschema` for the demo version comparison is **not** introduced; the demo
  `min_version`-vs-installed comparison reuses `update.py`'s existing version
  comparison primitive (DRY). If — and only if — that primitive is not already
  PEP 440-robust, a pinned `packaging` is added (confirmed during planning;
  flagged before adding).

## 7. Enforcement layers

1. **Pre-commit** — `check-jsonschema` validates `card.json` ↔ schema; a broken
   file cannot be committed locally.
2. **CI** — the existing "lint · type · lock · pre-commit" job runs
   `pre-commit run --all-files`, so the same hook gates the PR with no new,
   separate CI job required (verified during planning; if that job does not run
   all hooks, a dedicated schema-validation CI step is added).
3. **Deploy is `main`-only** — since 1+2 gate `main`, an invalid `card.json`
   structurally cannot reach Pages.
4. **Runtime** — §5 re-validates the fetched/cached bytes against the packaged
   schema before parsing; a broken served file → friendly #6 screen, never
   garbage.
5. **Drift test** (Hypothesis) — for arbitrary JSON documents, "valid per the
   JSON Schema" ⟺ "`parse_card` succeeds". Neither layer is dead weight; neither
   can silently diverge from the other.

## 8. Demos UX (both signals; named)

- `update_available` (a newer release exists on PyPI) is the existing,
  **unchanged** `update.py` signal that already drives the general startup notice
  and the current Demos badge.
- `new_demos(card, installed_version)` = the demos whose `min_version` is
  strictly greater than the installed package version (compared via
  `update.py`'s primitive).
- **Demos entry/panel** shows the named badge **iff** `update_available` **and**
  `new_demos` is non-empty: a header (e.g. "New demos in a newer
  henry-castillo — run `henry-castillo --update`") followed by one
  `● <name> — <summary>` line per new demo (rich `Text`, markup-safe).
- Otherwise the entry stays plain `Demos (under construction)` with no badge.
- The general "update available" startup notice (existing, throttled, TTY-only,
  offline-safe) is **untouched**: newer release + no new demos → general notice
  only; newer release + new demos → general notice **and** the named Demos badge;
  no newer release → neither (plain entry).
- No `demos` subcommand is added; the demos themselves remain a deferred `lab`
  stub. This change is purely the menu badge + the manifest that powers it.

## 9. `web/data/card.json`

Bump to `schema_version: 2`, add `demos: []`, add the `"$schema"` annotation.
All other content unchanged (DRAFT placeholders remain the maintainer's to fill;
projects unchanged incl. the private `nano-gpt-pretrain-steer` URL). `web/`
stays zero-runtime-dependency: `build.mjs` remains a pure staging copy (it also
stages `data/card.schema.json` alongside `data/card.json`); the repo file's
schema-conformance is guaranteed by the pre-commit/CI hook before it can reach
`main`/deploy.

## 10. Testing strategy (unchanged bar)

- Strict `demos` parse matrix (each required field missing/empty/wrong-type,
  bad `min_version`, non-list, extra key → `CardError` with the right path;
  valid → exact `Demo`s; `$schema` annotation accepted & ignored).
- Schema artifact tests: the schema is itself a valid Draft 2020-12 schema;
  `additionalProperties:false` rejects stray keys at every level; `const:2`
  rejects other `schema_version`s; the real `web/data/card.json` validates
  against it.
- Runtime schema gate: a fetched body that is JSON-valid but schema-invalid →
  `CardError` → #6 screen + `logger.error`; a schema-valid body proceeds to
  `parse_card`. Packaged-schema == web-schema byte-equality test.
- **Drift property** (Hypothesis): JSON Schema validity ⟺ `parse_card` success
  over arbitrary documents.
- `new_demos` version-comparison edge cases (equal → not new; pre/post/rc;
  installed ahead of all; demo exactly one patch ahead).
- Demos badge truth table (4 cells: ±`update_available` × ±`new_demos`) — the
  named list appears in exactly the (True, non-empty) cell, plain otherwise;
  the general notice's behavior is provably unchanged. `Text`-everywhere markup
  safety on demo `name`/`summary`.
- Integration/smoke (after push): the real schema-2 `web/data/card.json` →
  plain Demos entry, no badge, schema-valid at runtime; an injected card with a
  demo whose `min_version` > installed + a stubbed newer release → named badge,
  names/summaries sanitized; pre-commit `check-jsonschema` rejects a deliberately
  broken card fixture.
- Gate unchanged: exactly 100% line+branch, zero `# pragma: no cover` in `src/`,
  ruff/ruff-format/ty/pre-commit/zizmor/dependency-age (incl. `jsonschema` +
  the new hook)/`uv lock --locked`/`make check`, all CI checks green,
  Python 3.10-safe.

## 11. Scope / delivery

Additional conventional commits on `milestone-2-cli` / **PR #3** (unmerged — one
cohesive reviewable unit; the maintainer reviews & merges, never auto-merge).
Subagent-driven per-task two-stage reviews (spec then quality) + corrective
loops + a final whole-implementation review, then push, all CI checks green,
then real-data/API smoke. This must land **before** the maintainer merges PR #3
so the first deployed `card.json` is schema-2 / final-shaped. Spec and plan are
kept untracked per the standing preference.
