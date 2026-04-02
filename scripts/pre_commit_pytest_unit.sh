#!/usr/bin/env bash
set -euo pipefail
root="$(git rev-parse --show-toplevel 2>/dev/null)" || root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m pytest -m "not celery and not django" -q "$@"
elif [[ -x .venv/bin/python3 ]]; then
  exec .venv/bin/python3 -m pytest -m "not celery and not django" -q "$@"
else
  exec python3 -m pytest -m "not celery and not django" -q "$@"
fi
