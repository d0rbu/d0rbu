# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab) rather than a
public issue. You will get an acknowledgement within a reasonable timeframe.

## Supported versions

This project is pre-1.0; only the latest released version is supported.

## Automated hardening

Supply-chain measures (defense in depth against compromised dependencies and
Actions):

- **All GitHub Actions are pinned to full commit SHAs** (with `# vX.Y.Z`
  comments); `zizmor`'s `unpinned-uses` policy enforces `hash-pin` repo-wide,
  so a moved or compromised tag cannot inject code.
- **Dependabot** runs weekly for all ecosystems (uv, github-actions, npm)
  with a **≥7-day release cooldown** so a freshly compromised or yanked
  release is not auto-proposed, and keeps the pinned SHAs current.
- **Rolling ≥7-day minimum age for newly added or upgraded dependencies**
  (`scripts/check_min_dependency_age.py`). The baseline is the lockfiles at
  `origin/main`; a pinned `(name, version)` that is **added or
  version-changed** versus that baseline must have been published at least
  7 days ago. Pins unchanged from the baseline are grandfathered — the
  already-vetted committed lock is the trusted baseline; the supply-chain
  threat is a *new or upgraded* fresh release entering, not a pin that was
  already there. This is the same semantics as Dependabot's `cooldown`,
  applied to any lock bump (manual or Dependabot) once it would land — not a
  retroactive audit of the whole lockfile. Pre-commit runs it offline
  (uv.lock records each package's `upload-time`); CI runs the full check
  (uv.lock offline + npm candidates resolved against the npm registry).
  Neither `uv` nor `npm` has a native *rolling* minimum-release-age setting at
  the lock layer — Dependabot's cooldown only gates Dependabot's own PRs — so
  this guard supplies that missing protection for new/changed deps. The first
  PR that introduces the lockfiles (no committed lock at `origin/main`) is
  *baseline-establishing* and passes, listing the young deps for visibility;
  every subsequent bump is enforced. A confirmed too-fresh added/upgraded
  package fails the check; a transient npm-registry lookup error is a warning,
  not a block. The guard resolves lock paths to a repository-relative pathspec
  before reading the baseline (`git show <ref>:<path>`), so an absolute or
  otherwise non-repo-relative `--uv-lock`/`--npm-lock` cannot make the baseline
  read silently fail and degrade to a false "establishing" pass; a path
  outside the repository is a hard error, not a silent skip. The guard also
  **fails closed on an unverifiable added/upgraded dependency**: an added pin
  that looks like a registry package but whose age cannot be confirmed — a
  uv `registry`-source pin with a missing/unparseable `upload-time`, or an
  npm registry-shaped pin (concrete semver, not a link/file/git/workspace
  entry) whose `resolved` was stripped — is a hard violation, not a silent
  skip, so a hand-tampered lock cannot bypass the cooldown by scrubbing the
  age marker. Genuine non-registry entries (editable/virtual/directory/git/
  path/root for uv; `link:`/`file:`/`git+`/`git:`/workspace for npm)
  legitimately have no registry publish time and are not age-checked.
- **OpenSSF Scorecard** scores the repo's supply-chain posture weekly and
  uploads results to code scanning.
- **SLSA build provenance** (`actions/attest-build-provenance`) is signed for
  every published wheel/sdist in the release workflow.
- **npm `ignore-scripts=true`** (`packages/npm/.npmrc`) blocks arbitrary
  dependency lifecycle scripts; installs also use `engine-strict` and
  `save-exact`.
- `gitleaks` (pre-commit + CI) blocks committed secrets.
- `pip-audit` (CI) flags vulnerable Python dependencies; `npm audit`
  (CI, `--audit-level=high`) flags vulnerable npm dependencies.
- `zizmor` (CI) statically analyzes GitHub Actions workflows.
- CodeQL scans Python and TypeScript on a schedule and on PRs.
