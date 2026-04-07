#!/usr/bin/env bash
# macOS-only dev dependency checker (local machines only; not used in CI).
# Assumes git is already installed.
# - Default: summarize missing deps, then prompt [y/n/a] per step (a = yes to this and all following).
# - --dry-run: only list missing deps (one line each).
# - -y/--yes: non-interactive install (macOS + brew + pyenv); does not change pyenv global.
#
# Usage:
#   ./scripts/check_dev_dependencies.sh
#   ./scripts/check_dev_dependencies.sh --dry-run
#   ./scripts/check_dev_dependencies.sh -y
#
# Optional environment:
#   MIN_PYTHON_MAJOR     default: 3
#   MIN_PYTHON_MINOR     default: 10
#   PYENV_PYTHON_VERSION default: 3.12.8

set -uo pipefail

MIN_PYTHON_MAJOR="${MIN_PYTHON_MAJOR:-3}"
MIN_PYTHON_MINOR="${MIN_PYTHON_MINOR:-10}"
PYENV_PYTHON_VERSION="${PYENV_PYTHON_VERSION:-3.12.8}"

AUTO_YES=0
DRY_RUN=0
SHOW_HELP=0
# Set to 1 after user answers "a" at an interactive prompt (yes to all remaining).
PROMPT_ALL_FOLLOWING=0

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

is_macos() {
  [[ "$(uname -s)" == "Darwin" ]]
}

usage() {
  cat <<EOF
Usage: check_dev_dependencies.sh [options]

  macOS only (Homebrew). Exits with an error on other systems (except -h/--help).

  (no args)   Summarize missing dependencies, then prompt [y/n/a] for each install.
              y=yes, n=no, a=yes to this and all following prompts. Does not change pyenv global.

  -y, --yes   Non-interactive: install via Homebrew + pyenv.

  --dry-run   Print only missing dependencies (one line each). No prompts or installs.

  -h, --help  Show this help.

Environment: MIN_PYTHON_MAJOR, MIN_PYTHON_MINOR (defaults 3 and 10).
             PYENV_PYTHON_VERSION (default ${PYENV_PYTHON_VERSION})
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -y | --yes)
        AUTO_YES=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h | --help)
        SHOW_HELP=1
        shift
        ;;
      *)
        printf 'error: unknown option: %s\n' "$1" >&2
        usage >&2
        exit 2
        ;;
    esac
  done
}

require_brew() {
  if ! have_cmd brew; then
    printf 'error: Homebrew (brew) must be on PATH.\n' >&2
    exit 2
  fi
}

brew_install() {
  local formula=$1
  info "brew install ${formula} ..."
  brew install "${formula}"
}

pyenv_path_for_script() {
  export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
  if [[ -d "${PYENV_ROOT}/bin" ]]; then
    export PATH="${PYENV_ROOT}/bin:${PATH}"
  fi
  hash -r
}

pyenv_version_installed() {
  local root="${PYENV_ROOT:-$HOME/.pyenv}"
  [[ -x "${root}/versions/${PYENV_PYTHON_VERSION}/bin/python3" ]]
}

python_version_low() {
  have_cmd python3 || return 1
  local major minor
  major="$(python3 -c 'import sys; print(sys.version_info.major)' 2>/dev/null)" || return 1
  minor="$(python3 -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)" || return 1
  if [[ -z "${major:-}" || -z "${minor:-}" ]]; then
    return 1
  fi
  if ((major > MIN_PYTHON_MAJOR)); then
    return 1
  fi
  if ((major == MIN_PYTHON_MAJOR && minor >= MIN_PYTHON_MINOR)); then
    return 1
  fi
  return 0
}

prompt_yna() {
  local msg=$1
  local r
  if [[ "${PROMPT_ALL_FOLLOWING}" -eq 1 ]]; then
    info "(yes to all remaining) ${msg}"
    return 0
  fi
  if [[ ! -t 0 ]]; then
    return 1
  fi
  read -r -p "${msg} [y/n/a] " r </dev/tty || true
  case "${r}" in
    [aA])
      PROMPT_ALL_FOLLOWING=1
      return 0
      ;;
    [yY] | [yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

install_pyenv_brew_if_missing() {
  have_cmd pyenv && return 0
  require_brew
  brew_install pyenv
  pyenv_path_for_script
}

install_pyenv_brew_if_missing_interactive() {
  have_cmd pyenv && return 0
  if ! have_cmd brew; then
    warn "Homebrew (brew) not on PATH; cannot install pyenv."
    return 1
  fi
  if prompt_yna "Install pyenv via Homebrew?"; then
    brew_install pyenv
    pyenv_path_for_script
  fi
}

install_pyenv_python_if_needed() {
  install_pyenv_brew_if_missing
  pyenv_path_for_script
  if ! have_cmd pyenv; then
    warn "[error] pyenv not on PATH after install"
    return 1
  fi
  info "pyenv install -s ${PYENV_PYTHON_VERSION}"
  info "(does not change pyenv global; your default python3 on PATH stays as before)"
  pyenv install -s "${PYENV_PYTHON_VERSION}"
  info "Use this interpreter: pyenv shell ${PYENV_PYTHON_VERSION}  or  pyenv local ${PYENV_PYTHON_VERSION}  in a repo"
}

install_pyenv_python_if_needed_interactive() {
  pyenv_path_for_script
  if ! have_cmd pyenv; then
    return 0
  fi
  if have_cmd python3 && ! python_version_low && pyenv_version_installed; then
    return 0
  fi
  if prompt_yna "Install Python ${PYENV_PYTHON_VERSION} via pyenv (does not change pyenv global or your default python3)?"; then
    info "pyenv install -s ${PYENV_PYTHON_VERSION}"
    pyenv install -s "${PYENV_PYTHON_VERSION}"
  fi
}

pip_ensure_if_needed() {
  have_cmd python3 || return 0
  if python3 -m pip --version &>/dev/null; then
    return 0
  fi
  info "Running python3 -m ensurepip --upgrade ..."
  python3 -m ensurepip --upgrade 2>/dev/null || true
}

pip_ensure_if_needed_interactive() {
  have_cmd python3 || return 0
  if python3 -m pip --version &>/dev/null; then
    return 0
  fi
  if prompt_yna "Run python3 -m ensurepip --upgrade for the default python3 on PATH?"; then
    python3 -m ensurepip --upgrade 2>/dev/null || true
  fi
}

install_pkg_config_if_needed() {
  require_brew
  have_cmd pkg-config && return 0
  brew_install pkg-config
}

install_pkg_config_if_needed_interactive() {
  have_cmd pkg-config && return 0
  if ! have_cmd brew; then
    return 0
  fi
  if prompt_yna "Install pkg-config via Homebrew?"; then
    brew_install pkg-config
  fi
}

run_install_pass_yes() {
  [[ "${DRY_RUN}" -eq 1 ]] && return 0
  [[ "${AUTO_YES}" -eq 1 ]] || return 0
  section "Install (-y)"
  install_pyenv_python_if_needed
  pip_ensure_if_needed
  install_pkg_config_if_needed
}

run_interactive_install() {
  [[ "${DRY_RUN}" -eq 1 ]] && return 0
  [[ "${AUTO_YES}" -eq 1 ]] && return 0

  local summary
  summary="$(dry_run_print_missing)"
  if [[ -z "${summary}" ]]; then
    return 0
  fi

  info ""
  info "=== Missing dependencies ==="
  printf '%s\n' "${summary}"
  info ""

  if ! have_cmd brew; then
    warn "Homebrew (brew) not on PATH; cannot install automatically. See https://brew.sh — or run with -y once brew is available."
    return 0
  fi
  if [[ ! -t 0 ]]; then
    info "Not a terminal (stdin is not a TTY); skipping prompts. Use -y to install without prompts."
    return 0
  fi

  section "Interactive install"
  PROMPT_ALL_FOLLOWING=0
  info "Each prompt: y=yes, n=no, a=yes to this and all following installs."
  install_pyenv_brew_if_missing_interactive
  pyenv_path_for_script
  install_pyenv_python_if_needed_interactive
  pip_ensure_if_needed_interactive
  install_pkg_config_if_needed_interactive
}

dry_run_print_missing() {
  if ! have_cmd python3; then
    printf '%s\n' "missing:python3"
  else
    local major minor
    major="$(python3 -c 'import sys; print(sys.version_info.major)' 2>/dev/null)"
    minor="$(python3 -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)"
    if [[ -n "${major:-}" && -n "${minor:-}" ]]; then
      if ((major < MIN_PYTHON_MAJOR)) || { ((major == MIN_PYTHON_MAJOR)) && ((minor < MIN_PYTHON_MINOR)); }; then
        printf '%s\n' "missing:python>=${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR} (default python3 is ${major}.${minor})"
      fi
    fi
    if ! python3 -m pip --version &>/dev/null; then
      printf '%s\n' "missing:pip"
    fi
  fi

  if ! have_cmd pyenv; then
    printf '%s\n' "optional:pyenv"
  elif ! pyenv_version_installed; then
    printf '%s\n' "optional:pyenv-python-${PYENV_PYTHON_VERSION}"
  fi

  if ! have_cmd pkg-config; then
    printf '%s\n' "optional:pkg-config"
  fi
}

check_python() {
  if ! have_cmd python3; then
    warn "[missing] python3 on PATH — install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ (e.g. pyenv install ${PYENV_PYTHON_VERSION})"
    return
  fi

  local py_path
  py_path="$(command -v python3)"
  local ver
  ver="$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>/dev/null || echo "unknown")"
  info "[ok] default python3: $py_path ($ver)"

  local major minor
  major="$(python3 -c 'import sys; print(sys.version_info.major)' 2>/dev/null)"
  minor="$(python3 -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)"
  if [[ -n "${major:-}" && -n "${minor:-}" ]]; then
    if ((major < MIN_PYTHON_MAJOR)) || { ((major == MIN_PYTHON_MAJOR)) && ((minor < MIN_PYTHON_MINOR)); }; then
      warn "[version] default python3 is ${major}.${minor}; project may need ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+"
      if pyenv_version_installed; then
        info "       pyenv has ${PYENV_PYTHON_VERSION} — try: pyenv shell ${PYENV_PYTHON_VERSION}  (pyenv global unchanged)"
      else
        info "       e.g. pyenv install ${PYENV_PYTHON_VERSION}  then  pyenv local ${PYENV_PYTHON_VERSION}"
      fi
    fi
  fi

  if python3 -m pip --version &>/dev/null; then
    info "[ok] pip (via default python3 -m pip)"
  else
    warn "[missing] pip for default python3 — try: python3 -m ensurepip --upgrade"
  fi
}

check_pyenv_optional() {
  section "Optional: Python version management"
  if have_cmd pyenv; then
    info "[ok] pyenv: $(command -v pyenv)"
    if pyenv --version &>/dev/null; then
      info "     $(pyenv --version 2>/dev/null)"
    fi
    if pyenv_version_installed; then
      info "[ok] pyenv has Python ${PYENV_PYTHON_VERSION} at ~/.pyenv/versions/${PYENV_PYTHON_VERSION}"
    fi
  else
    info "[optional] pyenv not found — https://github.com/pyenv/pyenv (install with: brew install pyenv)"
  fi
}

check_build_essentials_hint() {
  section "Optional: native extension builds"
  if have_cmd pkg-config; then
    info "[ok] pkg-config: $(command -v pkg-config)"
  else
    info "[hint] pkg-config not found — some pip packages (e.g. database drivers) need:"
    info "       xcode-select --install  (Apple Command Line Tools) and/or: brew install pkg-config"
  fi
}

main() {
  parse_args "$@"
  if [[ "${SHOW_HELP}" -eq 1 ]]; then
    usage
    exit 0
  fi

  if ! is_macos; then
    printf 'error: this script supports macOS only.\n' >&2
    exit 2
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    dry_run_print_missing
    exit 0
  fi

  if [[ "${AUTO_YES}" -eq 1 ]]; then
    require_brew
  fi

  info "Dev dependency check (informational; not a gate)"
  if [[ "${AUTO_YES}" -eq 1 ]]; then
    info "Mode: -y (Homebrew + pyenv install; does not run pyenv global)"
  elif [[ -t 0 ]]; then
    info "Mode: interactive (summary, then [y/n/a]; use -y to skip prompts)"
  fi

  run_install_pass_yes
  run_interactive_install

  section "Python"
  check_python
  check_pyenv_optional
  check_build_essentials_hint

  section "Summary"
  info "Done. Optional tools are suggestions only; use whatever matches your workflow."
  if ((warn_count > 0)); then
    info "Warnings/recommendations: ${warn_count} (see above)"
  fi
  exit 0
}

main "$@"
