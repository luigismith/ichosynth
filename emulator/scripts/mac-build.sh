#!/usr/bin/env bash
# mac-build.sh — one command to build a ready-to-run macOS app of the NI404
# emulator. Installs the toolchain if needed, builds with Homebrew GCC (the
# firmware needs -fpermissive, which Clang lacks), bundles SDL2 so nothing else
# has to be installed, and drops the result in emulator/dist-macos/.
#
#   cd emulator/scripts && ./mac-build.sh
#
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"          # emulator/
repo="$(cd "$root/.." && pwd)"          # repo root (holds _SDCARD)
build="$root/build"
dist="$root/dist-macos/NI404-emulator-macOS"

echo "== NI404 emulator: macOS build =="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew non trovato. Installalo da https://brew.sh e riavvia." >&2
  exit 1
fi

echo "-- Installo/aggiorno toolchain (gcc, sdl2, cmake, dylibbundler)..."
brew list gcc          >/dev/null 2>&1 || brew install gcc
brew list sdl2         >/dev/null 2>&1 || brew install sdl2
brew list cmake        >/dev/null 2>&1 || brew install cmake
brew list dylibbundler >/dev/null 2>&1 || brew install dylibbundler

# Pick the newest Homebrew g++ (g++-14, g++-15, ...).
GXX="$(ls "$(brew --prefix)"/bin/g++-* 2>/dev/null | sort -V | tail -n1 || true)"
if [ -z "${GXX:-}" ]; then echo "Homebrew g++ non trovato dopo l'installazione di gcc." >&2; exit 1; fi
GCC="${GXX/g++/gcc}"
echo "-- Compilatore: $GXX"

echo "-- Configuro..."
cmake -S "$root" -B "$build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="$GCC" \
  -DCMAKE_CXX_COMPILER="$GXX" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix sdl2)" \
  -DNI404_SDCARD_PATH=_SDCARD

echo "-- Compilo ni404emu..."
cmake --build "$build" --target ni404emu -j"$(sysctl -n hw.ncpu)"
# toernemu only if the TŒRN source is present; never fail the script over it.
cmake --build "$build" --target toernemu -j"$(sysctl -n hw.ncpu)" 2>/dev/null || true

echo "-- Impacchetto (bundle SDL2 + campioni)..."
rm -rf "$dist"; mkdir -p "$dist/libs"
cp "$build/ni404emu" "$dist/"
[ -f "$build/toernemu" ] && cp "$build/toernemu" "$dist/" || true
[ -f "$root/MANUALE.md" ] && cp "$root/MANUALE.md" "$dist/" || true
[ -f "$root/playable-2026-06-13/midi-map.txt" ] && cp "$root/playable-2026-06-13/midi-map.txt" "$dist/" || true

for b in "$dist"/ni404emu "$dist"/toernemu; do
  [ -f "$b" ] || continue
  dylibbundler -od -b -x "$b" -d "$dist/libs" -p @executable_path/libs/ || true
  # dylibbundler can add the @executable_path/libs/ rpath once per relocated
  # dependency; duplicate LC_RPATH entries make dyld abort. Collapse to one.
  while install_name_tool -delete_rpath @executable_path/libs/ "$b" 2>/dev/null; do :; done
  install_name_tool -add_rpath @executable_path/libs/ "$b"
done

# Ship the sample card next to the binary (it looks for ./_SDCARD at runtime).
cp -R "$repo/_SDCARD" "$dist/_SDCARD"
rm -f "$dist/_SDCARD/wavmaker.exe" "$dist/_SDCARD/"*.bak2 2>/dev/null || true

cat > "$dist/LEGGIMI.txt" <<'TXT'
Emulatore NI404 — build macOS
=============================
Avvia da questa cartella:   ./ni404emu        (oppure ./ni404emu --demo)
Trascina un .wav nella finestra per caricarlo come campione.
Se macOS blocca l'avvio (Gatekeeper), una volta sola:
    xattr -dr com.apple.quarantine .
Manuale completo: MANUALE.md
TXT

echo ""
echo "== FATTO =="
echo "Cartella:  $dist"
echo "Avvia:     cd \"$dist\" && ./ni404emu --demo"
echo "(Se serve, prima:  xattr -dr com.apple.quarantine \"$dist\")"
