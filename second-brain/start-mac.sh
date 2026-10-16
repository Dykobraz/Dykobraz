#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
[[ -x .venv/bin/python ]] || { echo 'Nejprve spusť bash setup-mac.sh' >&2; exit 1; }
umask 077
exec .venv/bin/python server.py
