#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHEN="${1:-}"

if [[ -z "$WHEN" ]]; then
  echo "Usage: $0 WHEN" >&2
  echo "Example: $0 today" >&2
  exit 1
fi

source "$SCRIPT_DIR/venv/bin/activate"
exec python "$SCRIPT_DIR/purchase.py" "$WHEN"
