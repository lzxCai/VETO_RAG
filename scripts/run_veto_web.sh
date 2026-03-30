#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python >/dev/null 2>&1; then
  echo "未找到 python，请先激活项目环境（推荐 conda activate veto311）。" >&2
  exit 1
fi

if ! python - <<'PY'
import sys
major, minor = sys.version_info[:2]
sys.exit(0 if (major, minor) >= (3, 10) and (major, minor) < (3, 13) else 1)
PY
then
  echo "当前 python 版本不兼容。请先切到 Python 3.10-3.12（推荐 conda activate veto311）。" >&2
  python -V >&2 || true
  exit 1
fi

PORT="${PORT:-8000}"
RELOAD="${VETO_RELOAD:-0}"

echo "VETO web 正在启动..."
echo "启动后打开: http://127.0.0.1:${PORT}/veto"

if [[ "$RELOAD" == "1" ]]; then
  exec python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port "$PORT"
fi

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
