#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
[[ "$(uname -s)" == Darwin ]] || { echo 'Tento instalátor je určen pro macOS.' >&2; exit 1; }
command -v brew >/dev/null || { echo 'Nejprve nainstaluj Homebrew podle https://brew.sh' >&2; exit 1; }
python_prefix=$(brew --prefix python@3.12 2>/dev/null || true)
if [[ -z "$python_prefix" || ! -x "$python_prefix/bin/python3.12" ]]; then
  brew install python@3.12
  python_prefix=$(brew --prefix python@3.12)
fi
"$python_prefix/bin/python3.12" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
echo 'Second Brain je nainstalovaný. Spusť bash start-mac.sh'
