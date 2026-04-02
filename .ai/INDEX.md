# xa-transactions — agent context

## What this is

Python **3.10+** library: coordinate **MySQL XA (two-phase commit)** across **parallel workers** (e.g. Celery) with **atomic commit or rollback** across branches. Optional **Django** and **Celery** integrations.

## Where code lives

| Area | Path | Role |
|------|------|------|
| Coordinator, XA adapter, MySQL store | `xa_transactions/core/` | Orchestration, XA SQL, durable branch/global state |
| Integrations | `xa_transactions/integrations/` | Celery (`celery` extra), Django (optional) |
| Recovery, connections | `xa_transactions/infrastructure/` | Recovery strategy, connection factories |
| Types & protocols | `xa_transactions/types/` | `StoreProtocol`, `XAAdapterProtocol`, errors, XID types |
| Observability | `xa_transactions/observability/` | Hooks and metrics helpers |
| Public exports | `xa_transactions/__init__.py` | Stable surface for imports |

## Human docs (read before large design changes)

- [README.md](../README.md) — overview and quick start
- [ARCHITECTURE.md](../ARCHITECTURE.md) — design detail
- [docs/CELERY.md](../docs/CELERY.md) — Celery usage
- [docs/DJANGO.md](../docs/DJANGO.md) — Django usage

## Local environment

Use a **venv** and **pip** — see **Development** in [README.md](../README.md) (`python3 -m venv .venv`, activate, `pip install -e ".[dev]"`). Optional: [scripts/check_dev_dependencies.sh](../scripts/check_dev_dependencies.sh) (**macOS only**, **Homebrew**; assumes **git**; interactive **y/n/a**; **`--dry-run`** / **`-y`**) then [scripts/setup_local_env.sh](../scripts/setup_local_env.sh) (venv + editable install).

## Verify changes

- **Pre-commit** (required): `pip install -e ".[dev]"` includes the `pre-commit` package; run **`pre-commit install`** once per clone (or use [scripts/setup_local_env.sh](../scripts/setup_local_env.sh) with default `PIP_EXTRAS=dev`). Hooks: Ruff (`xa_transactions/`, `tests/` only, same as CI) + unit-only `pytest` ([.pre-commit-config.yaml](../.pre-commit-config.yaml), [scripts/pre_commit_pytest_unit.sh](../scripts/pre_commit_pytest_unit.sh)). Manual: `pre-commit run --all-files`.
- **Lint / format**: `ruff check xa_transactions tests` and `ruff format --check xa_transactions tests` (after `pip install -e ".[dev]"`; see [README.md](../README.md)).
- **Unit tests + coverage**: `pytest --cov=xa_transactions --cov-report=term-missing` (default run skips `@pytest.mark.celery` / `django` tests; see **Testing** in README).
- **Optional integration tests**: `pip install -e ".[dev,celery,django]"` then `pytest -m "celery or django" -v`.
- **CI**: [.github/workflows/ci.yml](../.github/workflows/ci.yml) — matrix 3.10–3.12 on Ubuntu; tag releases only on green CI.

## Conventions for edits

- Prefer **type hints** (`T | None`, not `Optional[T]`, without relying on `from __future__ import annotations` — **Python 3.10+** is required).
- Treat **`StoreProtocol`** and **`xa_transactions/__init__.py`** exports as API: breaking changes need intent and changelog consideration.
- Optional deps: Celery/Django code paths should remain import-safe when extras are not installed (see patterns in `__init__.py`).
