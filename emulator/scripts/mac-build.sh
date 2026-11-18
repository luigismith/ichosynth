#!/usr/bin/env bash
# mac-build.sh — one command to build a ready-to-run macOS package of the emulator:
# toernemu (the real TŒRN firmware, staged by firmware/build_toern.py) and ni404emu
# (the legacy bench). Installs the toolchain if needed and builds with Homebrew GCC:
# the Arduino sketches need GCC's -fpermissive, which Apple Clang does not honour.
# Consequence: no MIDI input on macOS (Apple's CoreMIDI headers use Clang-only block
# syntax, so src/midi_in.cpp compiles its no-MIDI stub under GCC); keyboard, mouse,
# audio, recording and drag-and-drop work. SDL2 is bundled, so nothing else has to be
# installed, and the result lands in emulator/dist-macos/.
#
#   cd emulator/scripts && ./mac-build.sh
#
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"          # emulator/
repo="$(cd "$root/.." && pwd)"          # repo root (holds sdcard)
build="$root/build"
dist="$root/dist-macos/ichosynth-emulator-macOS"

echo "== ichosynth emulator: macOS build =="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew non trovato. Installalo da https://brew.sh e riavvia." >&2
  exit 1
fi

echo "-- Installo/aggiorno toolchain (gcc, sdl2, cmake, python, dylibbundler)..."
brew list gcc          >/dev/null 2>&1 || brew install gcc
brew list sdl2         >/dev/null 2>&1 || brew install sdl2
brew list cmake        >/dev/null 2>&1 || brew install cmake
brew list python       >/dev/null 2>&1 || brew install python
brew list dylibbundler >/dev/null 2>&1 || brew install dylibbundler

# Pick the newest Homebrew g++ (g++-14, g++-15, ...).
GXX="$(ls "$(brew --prefix)"/bin/g++-* 2>/dev/null | sort -V | tail -n1 || true)"
if [ -z "${GXX:-}" ]; then echo "Homebrew g++ non trovato dopo l'installazione di gcc." >&2; exit 1; fi
GCC="${GXX/g++/gcc}"
PY="$(command -v python3)"
echo "-- Compilatore: $GXX   Python: $PY"

echo "-- Sorgenti TŒRN al commit fissato in firmware/build_toern.py (clonati se mancano; serve git)..."
"$PY" "$repo/firmware/build_toern.py" --fetch-only

jobs="$(( $(sysctl -n hw.ncpu) / 2 ))"; [ "$jobs" -lt 2 ] && jobs=2
echo "-- Configuro..."
nice -n 10 cmake -S "$root" -B "$build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="$GCC" \
  -DCMAKE_CXX_COMPILER="$GXX" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix sdl2)" \
  -DEMU_BUILD_TOERN=ON -DPython3_EXECUTABLE="$PY"

echo "-- Compilo toernemu + ni404emu (priorita' bassa)..."
nice -n 10 cmake --build "$build" --target toernemu ni404emu -j"$jobs"

echo "-- Impacchetto (bundle SDL2 + campioni)..."
rm -rf "$dist"; mkdir -p "$dist/libs"
cp "$build/toernemu" "$build/ni404emu" "$dist/"
[ -f "$root/MANUALE.md" ] && cp "$root/MANUALE.md" "$dist/" || true

for b in "$dist"/toernemu "$dist"/ni404emu; do
  dylibbundler -od -b -x "$b" -d "$dist/libs" -p @executable_path/libs/ || true
  # dylibbundler can add the @executable_path/libs/ rpath once per relocated
  # dependency; duplicate LC_RPATH entries make dyld abort. Collapse to one.
  while install_name_tool -delete_rpath @executable_path/libs/ "$b" 2>/dev/null; do :; done
  install_name_tool -add_rpath @executable_path/libs/ "$b"
done

# Ship the sample card next to the binary (it looks for ./sdcard at runtime).
cp -R "$repo/sdcard" "$dist/sdcard"
rm -f "$dist/sdcard/"*.bak2 2>/dev/null || true

cat > "$dist/LEGGIMI.txt" <<'TXT'
Emulatore ichosynth — build macOS
=================================
Avvia da questa cartella:   ./toernemu          (il firmware TŒRN reale dello strumento)
                            ./ni404emu --demo   (il vecchio firmware-banco NI404)
Trascina un file audio nella finestra: finisce sulla SD in samples/import/.
Su macOS non c'e' ingresso MIDI (build GCC): usa tastiera, mouse o trackpad.
Se macOS blocca l'avvio (Gatekeeper), una volta sola:
    xattr -dr com.apple.quarantine .
Manuale completo: MANUALE.md
TXT

echo ""
echo "== FATTO =="
echo "Cartella:  $dist"
echo "Avvia:     cd \"$dist\" && ./toernemu"
echo "(Se serve, prima:  xattr -dr com.apple.quarantine \"$dist\")"
