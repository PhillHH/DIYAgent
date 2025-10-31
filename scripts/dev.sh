#!/usr/bin/env bash
set -euo pipefail

HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8000}

if [[ ! -d '.venv' ]]; then
  echo "[dev.sh] Virtuelle Umgebung .venv nicht gefunden." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[dev.sh] Starte uvicorn auf ${HOST}:${PORT} (reload aktiv)."
uvicorn api.main:app --host "${HOST}" --port "${PORT}" --reload
