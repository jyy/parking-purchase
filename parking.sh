#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHEN="${1:-}"

if [[ -z "$WHEN" ]]; then
  echo "Usage: $0 WHEN" >&2
  echo "Example: $0 today" >&2
  exit 1
fi

if [[ -d "$SCRIPT_DIR/venv" ]]; then
  source "$SCRIPT_DIR/venv/bin/activate"
fi

# Send immediate feedback to Telegram if triggered via shell2telegram
if [[ -n "$TB_TOKEN" && -n "$S2T_CHATID" ]]; then
  python3 "$SCRIPT_DIR/telegram_notify.py" "⏳ Parking checkout in progress for $WHEN..." >/dev/null 2>&1 &
fi

exec python3 "$SCRIPT_DIR/purchase.py" "$WHEN"
