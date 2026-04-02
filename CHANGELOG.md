# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) style; use [Commitizen](https://commitizen-tools.github.io/commitizen/) (`git cz`) when committing.

## [Unreleased]

### Added

- **GitHub Actions:** [`.github/workflows/tag-on-main.yml`](.github/workflows/tag-on-main.yml) — on push to `main`, create `v<version>` from `pyproject.toml` if missing on the remote.

### Changed

### Fixed

### Removed

---

## [0.2.0] - 2026-04-02

### Added

- **XA `format_id`**: `XID` includes `format_id`; propagated through `MySQLXAAdapter`, `Coordinator`, `create_coordinator`, recovery (`DefaultRecoveryStrategy`), and Celery XA context (`XATask`, `xa_task`).
- **`py.typed`** marker for PEP 561 type-checker support.
- **`[tool.mypy]`** in `pyproject.toml` (aligned with Python 3.10).
- **Pre-commit**: `.pre-commit-config.yaml` — Ruff (lint + format) on `xa_transactions/` and `tests/`; unit-only `pytest` (excludes `celery` / `django` markers) via `scripts/pre_commit_pytest_unit.sh` (prefers `.venv/bin/python`).
- **`pre-commit`** in the `dev` optional dependency set; `scripts/setup_local_env.sh` runs `pre-commit install` when extras include `dev`.
- **CI** (GitHub Actions): unit job (Ruff + pytest with coverage) and integration job (Celery/Django marked tests) on Python 3.10–3.12.
- **Scripts**: `scripts/check_dev_dependencies.sh` (macOS/Homebrew helper), `scripts/setup_local_env.sh`.
- **`.ai/INDEX.md`**: agent-oriented repo overview and verification commands.
- **Integration smoke tests**: `tests/integration/` for `@pytest.mark.celery` and `@pytest.mark.django` (import/symbol checks).

### Changed

- **`requires-python`**: `>=3.10` (was `>=3.9` on the feature branch before merge).
- **Django integration**: `xa_aware_atomic` implemented with a `ContextDecorator`-style helper so Django’s `atomic` usage patterns (context manager, decorator, callable `using`) behave correctly.
- **README**: development setup, testing (unit vs integration), required pre-commit workflow.

### Fixed

- Django `transaction.atomic` wrapper behavior for all supported usage patterns.
- Typing and error-handling cleanups on the format-id / mypy branch.
- Ruff-driven import and style fixes in Django integration after merge.

### Removed

- (none noted)

---

## [0.1.0] - 2026-02-23

### Added

- Initial **xa-transactions** library: MySQL XA coordination (`Coordinator`, `MySQLXAAdapter`, `MySQLStore`), protocols, recovery, observability hooks/metrics, optional Celery and Django integrations.
- **Architecture** and diagram updates in-repo.

[Unreleased]: https://github.com/cube-planning/xa_transactions/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/cube-planning/xa_transactions/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cube-planning/xa_transactions/releases/tag/v0.1.0
