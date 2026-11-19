#!/usr/bin/env bash
# bootstrap-macos.sh — install the toolchain + SDL2 for the ichosynth emulator.
set -euo pipefail
echo "== ichosynth emulator: macOS toolchain bootstrap =="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install it from https://brew.sh then re-run." >&2
  exit 1
fi

# Xcode command-line tools: git, make and the macOS SDK. The compiler itself is
# Homebrew GCC (below), not Apple Clang.
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Installing Xcode command-line tools..."
  xcode-select --install || true
fi

echo "Installing gcc, cmake, SDL2, python, dylibbundler..."
# gcc (not clang): the Arduino sketches need GCC's -fpermissive.
# python: toernemu's CMake step runs firmware/build_toern.py.
# dylibbundler: makes the built app self-contained (bundles SDL2).
brew install gcc cmake sdl2 python dylibbundler

echo ""
echo "Toolchain ready. Build a ready-to-run app with:  ./mac-build.sh"
