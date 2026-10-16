#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
[[ -x .venv/bin/python && -x bin/seminar-capture ]] || { echo 'Nejdříve spusťte bash setup-mac.sh' >&2; exit 1; }
command -v ollama >/dev/null || { echo 'Chybí Ollama. Spusťte setup-mac.sh.' >&2; exit 1; }
ollama_pid=''
cleanup() {
  if [[ -n "$ollama_pid" ]]; then
    kill "$ollama_pid" 2>/dev/null || true
    wait "$ollama_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
if ! curl --noproxy '*' --fail --silent http://127.0.0.1:11434/api/tags >/dev/null; then
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 ollama serve &
  ollama_pid=$!
  ready=0
  for attempt in {1..30}; do
    if curl --noproxy '*' --fail --silent http://127.0.0.1:11434/api/tags >/dev/null; then ready=1; break; fi
    kill -0 "$ollama_pid" 2>/dev/null || break
    sleep 1
  done
  [[ "$ready" == 1 ]] || { echo 'Místní Ollama se nepodařilo spustit.' >&2; exit 1; }
fi
.venv/bin/python app.py
