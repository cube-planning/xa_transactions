#!/usr/bin/env bash
# Generic local environment setup (run after check_dev_dependencies.sh or on its own).
# Creates a venv if missing, upgrades pip, installs the project in editable mode with extras.
#
# Run from repository root, or from anywhere (script locates repo root as parent of scripts/).
#
# Environment (all optional):
#   PYTHON           Interpreter to create venv with (default: python3)
#   VENV_DIR         Relative path to venv (default: .venv)
#   PIP_EXTRAS       Comma-separated extras for editable install (default: dev)
#                    Example: dev  or  dev,celery
#   SKIP_PIP_UPGRADE If set to 1, skip "pip install -U pip"
#   REPO_ROOT        Override repository root (default: parent of scripts/)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
PIP_EXTRAS="${PIP_EXTRAS:-dev}"
SKIP_PIP_UPGRADE="${SKIP_PIP_UPGRADE:-0}"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

main() {
  cd "$REPO_ROOT" || die "cannot cd to REPO_ROOT: $REPO_ROOT"

  if [[ ! -f pyproject.toml && ! -f setup.cfg && ! -f setup.py ]]; then
    die "no pyproject.toml, setup.cfg, or setup.py in $REPO_ROOT — not a Python project root?"
  fi

  if ! command -v "$PYTHON" &>/dev/null; then
    die "interpreter not found: $PYTHON (set PYTHON=...)"
  fi

  local venv_path="$REPO_ROOT/$VENV_DIR"
  if [[ ! -d "$venv_path" ]]; then
    echo "Creating venv at $VENV_DIR using $PYTHON ..."
    "$PYTHON" -m venv "$venv_path"
  else
    echo "Using existing venv at $VENV_DIR"
  fi

  local py
  if [[ -x "$venv_path/bin/python" ]]; then
    py="$venv_path/bin/python"
  elif [[ -x "$venv_path/Scripts/python.exe" ]]; then
    py="$venv_path/Scripts/python.exe"
  else
    die "could not find venv python under $venv_path/bin or $venv_path/Scripts"
  fi

  if [[ "$SKIP_PIP_UPGRADE" != "1" ]]; then
    echo "Upgrading pip ..."
    "$py" -m pip install -U pip
  fi

  if [[ -f pyproject.toml ]] || [[ -f setup.cfg ]] || [[ -f setup.py ]]; then
    if [[ -n "${PIP_EXTRAS}" ]]; then
      echo "Installing editable package with extras .[${PIP_EXTRAS}] ..."
      "$py" -m pip install -e ".[${PIP_EXTRAS}]"
    else
      echo "Installing editable package (no extras) ..."
      "$py" -m pip install -e .
    fi
  else
    die "no pyproject.toml, setup.cfg, or setup.py found"
  fi

  if [[ "${PIP_EXTRAS}" == *"dev"* ]] && "$py" -m pre_commit --version &>/dev/null; then
    echo "Installing pre-commit git hooks ..."
    "$py" -m pre_commit install
  fi

  echo ""
  echo "Setup complete."
  echo "Activate the environment:"
  echo "  source ${VENV_DIR}/bin/activate          # Linux / macOS / Git Bash"
  echo "  ${VENV_DIR}\\\\Scripts\\\\activate.bat       # Windows cmd"
  echo "  ${VENV_DIR}\\\\Scripts\\\\Activate.ps1       # Windows PowerShell"
}

main "$@"
