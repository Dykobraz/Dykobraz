#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'Tento instalační skript je určen pro macOS.' >&2; exit 1
fi
command -v brew >/dev/null || { echo 'Nejdříve nainstalujte Homebrew podle https://brew.sh' >&2; exit 1; }
xcode-select -p >/dev/null 2>&1 || { echo 'Spusťte xcode-select --install a po instalaci tento skript zopakujte.' >&2; exit 1; }
brew install python@3.12 ollama
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p bin
xcrun swiftc -parse-as-library native/Capture.swift -o bin/seminar-capture \
  -framework ScreenCaptureKit -framework CoreMedia -framework AudioToolbox
echo 'Instalace dokončena. Pokračujte podle README.md: spuštění Ollama a stažení modelů.'
