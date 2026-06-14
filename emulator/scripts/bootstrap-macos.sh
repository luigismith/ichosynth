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

echo "Installing gcc, cmake, SDL2, dylibbundler..."
# gcc (not just clang): the firmware needs -fpermissive, which Clang lacks.
# dylibbundler: makes the built app self-contained (bundles SDL2).
brew install gcc cmake sdl2 dylibbundler

echo ""
echo "Toolchain ready. Build a ready-to-run app with:  ./mac-build.sh"
