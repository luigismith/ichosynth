#!/usr/bin/env bash
# build.sh — configure & build the NI404 emulator on macOS / Linux.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
build="$root/build"
mkdir -p "$build"
cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build" -j
echo ""
echo "Built: $build/ni404emu"
echo "Run with:  $build/ni404emu"
