#!/usr/bin/env bash
# bootstrap-macos.sh — install the C++ toolchain + SDL2 for the NI404 emulator.
set -euo pipefail
echo "== NI404 emulator: macOS toolchain bootstrap =="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install it from https://brew.sh then re-run." >&2
  exit 1
fi

# Xcode command-line tools provide clang++.
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Installing Xcode command-line tools..."
  xcode-select --install || true
fi

echo "Installing cmake and SDL2..."
brew install cmake sdl2

echo ""
echo "Toolchain ready. Now build with:  ./build.sh"
