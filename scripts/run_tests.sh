#!/usr/bin/env bash
set -euo pipefail
VENV_BIN="${VENV_BIN:-.venv/bin}"
PY="$VENV_BIN/python"
if [ ! -x "$PY" ]; then
  PY="python3"
fi
$PY -m unittest MCP.tests.test_validate_ubl
