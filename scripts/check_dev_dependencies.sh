#!/usr/bin/env bash
# Generic dev dependency checker.
# - Prints what's missing and suggested install hints.
# - Does NOT exit with failure for optional tools (e.g. pyenv); nothing here is mandatory to "pass".
#
# Optional environment:
#   MIN_PYTHON_MAJOR   default: 3
#   MIN_PYTHON_MINOR   default: 10   (warn if python3 is older than this)

set -uo pipefail

MIN_PYTHON_MAJOR="${MIN_PYTHON_MAJOR:-3}"
MIN_PYTHON_MINOR="${MIN_PYTHON_MINOR:-10}"

warn_count=0

warn() {
  printf '%s\n' "$*" >&2
  warn_count=$((warn_count + 1))
}

info() {
  printf '%s\n' "$*"
}

have_cmd() {
  command -v "$1" &>/dev/null
}

section() {
  info ""
  info "=== $* ==="
}

check_git() {
  if have_cmd git; then
    info "[ok] git: $(command -v git)"
  else
    warn "[missing] git — install: https://git-scm.com/downloads"
  fi
}

check_python() {
  if ! have_cmd python3; then
    warn "[missing] python3 — install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ from https://www.python.org/downloads/ or your OS package manager"
    return
  fi

  local py_path
  py_path="$(command -v python3)"
  local ver
  ver="$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>/dev/null || echo "unknown")"
  info "[ok] python3: $py_path ($ver)"

  local major minor
  major="$(python3 -c 'import sys; print(sys.version_info.major)' 2>/dev/null)"
  minor="$(python3 -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)"
  if [[ -n "${major:-}" && -n "${minor:-}" ]]; then
    if (( major < MIN_PYTHON_MAJOR )) || { (( major == MIN_PYTHON_MAJOR )) && (( minor < MIN_PYTHON_MINOR )); }; then
      warn "[version] python3 is ${major}.${minor}; this project may need ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ (adjust MIN_PYTHON_* if checking another codebase)"
    fi
  fi

  if python3 -m pip --version &>/dev/null; then
    info "[ok] pip (via python3 -m pip)"
  else
    warn "[missing] pip for python3 — try: python3 -m ensurepip --upgrade (or install python3-pip via your OS)"
  fi
}

check_pyenv_optional() {
  section "Optional: Python version management"
  if have_cmd pyenv; then
    info "[ok] pyenv: $(command -v pyenv)"
    if pyenv --version &>/dev/null; then
      info "     $(pyenv --version 2>/dev/null)"
    fi
  else
    info "[optional] pyenv not found — many teams use it to install/switch Python versions: https://github.com/pyenv/pyenv"
    info "           (You can use another workflow: asdf, conda, system packages, etc.)"
  fi
}

check_build_essentials_hint() {
  section "Optional: native extension builds"
  if have_cmd pkg-config; then
    info "[ok] pkg-config: $(command -v pkg-config)"
  else
    info "[hint] pkg-config not found — some pip packages (e.g. database drivers) need build tools:"
    info "       macOS: xcode-select --install; brew install pkg-config"
    info "       Debian/Ubuntu: sudo apt install build-essential pkg-config"
  fi
}

main() {
  info "Dev dependency check (informational; not a gate)"
  section "Core"
  check_git
  check_python
  check_pyenv_optional
  check_build_essentials_hint

  section "Summary"
  info "Done. Optional tools are suggestions only; use whatever matches your workflow."
  if (( warn_count > 0 )); then
    info "Warnings/recommendations: ${warn_count} (see above)"
  fi
  exit 0
}

main "$@"
