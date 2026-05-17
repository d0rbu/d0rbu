# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab) rather than a
public issue. You will get an acknowledgement within a reasonable timeframe.

## Supported versions

This project is pre-1.0; only the latest released version is supported.

## Automated hardening

- `gitleaks` (pre-commit + CI) blocks committed secrets.
- `pip-audit` (CI) flags vulnerable Python dependencies.
- `zizmor` (CI) statically analyzes GitHub Actions workflows.
- CodeQL scans Python and TypeScript on a schedule and on PRs.
- Dependabot keeps dependencies and Actions pinned and current.
