#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_AGENT_BROWSER_DIR="${ROOT_DIR}/third_party/agent-browser"
if [[ ! -d "${DEFAULT_AGENT_BROWSER_DIR}" ]]; then
  DEFAULT_AGENT_BROWSER_DIR="${ROOT_DIR}/demo/agent-browser"
fi
AGENT_BROWSER_DIR="${AGENT_BROWSER_DIR:-${DEFAULT_AGENT_BROWSER_DIR}}"

if [[ ! -d "${AGENT_BROWSER_DIR}" ]]; then
  echo "[setup] agent-browser dir not found: ${AGENT_BROWSER_DIR}" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[setup] node is required but not found." >&2
  exit 1
fi

echo "[setup] using agent-browser dir: ${AGENT_BROWSER_DIR}"
cd "${AGENT_BROWSER_DIR}"

INSTALL_OK=0
SETUP_PREFER_NPM="${AGENT_BROWSER_SETUP_PREFER_NPM:-0}"
if [[ "${SETUP_PREFER_NPM}" != "1" ]] && command -v pnpm >/dev/null 2>&1; then
  if [[ -f "pnpm-lock.yaml" ]]; then
    echo "[setup] try pnpm install --frozen-lockfile"
    if pnpm install --frozen-lockfile; then
      INSTALL_OK=1
    else
      echo "[setup] pnpm install failed, fallback to npm..."
    fi
  else
    echo "[setup] try pnpm install"
    if pnpm install; then
      INSTALL_OK=1
    else
      echo "[setup] pnpm install failed, fallback to npm..."
    fi
  fi
fi

if [[ "${INSTALL_OK}" -ne 1 ]]; then
  echo "[setup] npm install --legacy-peer-deps (HUSKY=0)"
  HUSKY=0 npm install --legacy-peer-deps
fi

echo "[setup] build daemon/runtime assets"
if command -v pnpm >/dev/null 2>&1; then
  pnpm run build || npm run build
else
  npm run build
fi

LOCAL_BIN="${AGENT_BROWSER_DIR}/bin/agent-browser.js"
if [[ ! -f "${LOCAL_BIN}" ]]; then
  echo "[setup] missing local wrapper: ${LOCAL_BIN}" >&2
  exit 1
fi

# postinstall should fetch native binary. If not present, fallback to local native build when rust toolchain exists.
if ! node "${LOCAL_BIN}" --version >/dev/null 2>&1; then
  if command -v cargo >/dev/null 2>&1; then
    echo "[setup] prebuilt native binary unavailable, trying local native build..."
    if command -v pnpm >/dev/null 2>&1; then
      pnpm run build:native || npm run build:native
    else
      npm run build:native
    fi
  else
    echo "[setup] local native binary unavailable and cargo not found." >&2
    echo "[setup] try re-run network-enabled install or install Rust toolchain for build:native." >&2
    exit 1
  fi
fi

echo "[setup] install playwright chromium runtime (may retry on slow network)"
if ! npx playwright install chromium; then
  echo "[setup] WARN: playwright chromium install failed. Web open may fail until this step succeeds."
fi

echo "[setup] smoke check: agent-browser --version"
node "${LOCAL_BIN}" --version
echo "[setup] smoke check: agent-browser --native open about:blank"
node "${LOCAL_BIN}" --native --json open about:blank >/dev/null
node "${LOCAL_BIN}" --native --json close >/dev/null || true

echo "[setup] done. To force runtime local path:"
echo "export AGENT_BROWSER_PROJECT_DIR='${AGENT_BROWSER_DIR}'"
echo "export AGENT_BROWSER_PREFER_LOCAL=1"
echo "export AGENT_BROWSER_FORCE_NATIVE=1"
