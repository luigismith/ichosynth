#!/usr/bin/env bash
# build.sh — configure & build the NI404 emulator on macOS / Linux.
# On macOS this is a thin wrapper around mac-build.sh (which uses Homebrew GCC and
# packages a self-contained app); the firmware needs -fpermissive, which the
# default macOS Clang lacks.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"
build="$root/build"

if [ "$(uname)" = "Darwin" ]; then
  exec "$here/mac-build.sh"
fi

mkdir -p "$build"
cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build" -j
echo ""
echo "Built: $build/ni404emu"
echo "Run with:  $build/ni404emu"
