#!/usr/bin/env bash
# build.sh — configure & build the emulator (toernemu + ni404emu) on macOS / Linux,
# at low priority. On macOS this is a thin wrapper around mac-build.sh (Homebrew GCC,
# packages a self-contained app): the Arduino sketches need GCC's -fpermissive.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"
build="$root/build"

if [ "$(uname)" = "Darwin" ]; then
  exec "$here/mac-build.sh"
fi

py="$(command -v python3)"
"$py" "$root/../firmware/build_toern.py" --fetch-only     # pinned TŒRN sources (needs git)
jobs="$(( $(nproc) / 2 ))"; [ "$jobs" -lt 2 ] && jobs=2
mkdir -p "$build"
nice -n 10 cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release -DEMU_BUILD_TOERN=ON -DPython3_EXECUTABLE="$py"
nice -n 10 cmake --build "$build" --target toernemu ni404emu -j "$jobs"
echo ""
echo "Built: $build/toernemu and $build/ni404emu"
echo "Run with:  $build/toernemu"
