#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# shellcheck disable=SC1091
source scripts/use_guiagent_v2_env.sh

python3 run.py \
  --runtime_mode guiagent_v2 \
  --v2_skip_legacy \
  --v2_enable_model_intent_parser \
  --v2_enable_model_web_replan \
  --v2_enable_model_assertion_repair \
  "$@"
