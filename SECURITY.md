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
