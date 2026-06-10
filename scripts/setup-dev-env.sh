#!/usr/bin/env bash
#
# ichosynth — one-shot dev-environment setup (macOS / Linux)
# ---------------------------------------------------------------------------
# Installs the Teensy core + every library the firmware needs, patches
# ResamplingReader.h, and compile-checks the sketch. Safe to re-run.
#
#   chmod +x scripts/setup-dev-env.sh
#   ./scripts/setup-dev-env.sh            # install + patch + compile
#   ./scripts/setup-dev-env.sh --no-build # skip the compile-check
#
# Requires arduino-cli (https://arduino.github.io/arduino-cli/). On macOS:
#   brew install arduino-cli
# ---------------------------------------------------------------------------
set -euo pipefail

BUILD=1
[[ "${1:-}" == "--no-build" ]] && BUILD=0

# repo root = parent of this script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"

TEENSY_URL="https://www.pjrc.com/teensy/package_teensy_index.json"
FQBN="teensy:avr:teensy41:usb=serialmidi16"   # Teensy 4.1, USB = Serial + MIDIx16

# registry libraries (exact names). FastLED is PINNED to 3.9.10 — newer 3.10.x
# break on the Teensy WS2812Serial controller path used by this firmware.
REGISTRY_LIBS=(
  "FastLED@3.9.10"
  "Mapf"
  "Switch"                       # avdweb_Switch (button gestures)
  "Adafruit SSD1306"             # OLED (only needed if OLED_ENABLED, harmless otherwise)
  "Adafruit GFX Library"
)
# The two newdigate libraries are developed together and must come from the SAME
# source — the registry copies are version-skewed against each other (missing
# AudioPlaySdResmp / playRaw / triggerReload). Install both from GitHub HEAD, in
# this order (teensy-polyphony depends on teensy-variable-playback).
GIT_LIBS=(
  "https://github.com/newdigate/teensy-variable-playback.git"  # AudioPlayArrayResmp + ResamplingReader.h
  "https://github.com/newdigate/teensy-polyphony.git"          # TeensyPolyphony (arraysampler)
)
# NOTE: WS2812Serial, Encoder, Audio, Wire, SD, EEPROM ship with the Teensy core.

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m   ✓ %s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m   ! %s\033[0m\n' "$*"; }

command -v arduino-cli >/dev/null 2>&1 || {
  echo "arduino-cli not found. Install it first:"
  echo "  macOS:  brew install arduino-cli"
  echo "  Linux:  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh"
  exit 1
}
ok "arduino-cli $(arduino-cli version | head -n1)"

say "Configuring arduino-cli (Teensy board URL + git installs)"
arduino-cli config init --overwrite >/dev/null 2>&1 || true
arduino-cli config set library.enable_unsafe_install true >/dev/null
arduino-cli config add board_manager.additional_urls "$TEENSY_URL" >/dev/null 2>&1 \
  || arduino-cli config set board_manager.additional_urls "$TEENSY_URL" >/dev/null
ok "config ready"

say "Installing the Teensy core (teensy:avr)"
arduino-cli core update-index >/dev/null
arduino-cli core install teensy:avr
ok "Teensy core installed"

say "Installing registry libraries"
arduino-cli lib update-index >/dev/null
arduino-cli lib install "${REGISTRY_LIBS[@]}"
ok "registry libraries installed"

say "Installing libraries from GitHub (named in the project README)"
# Remove any registry copies first so we don't end up with two libraries that
# both provide TeensyPolyphony.h / the variable-playback headers (duplicate
# library = header conflict). The registry copies are also version-skewed.
arduino-cli lib uninstall "TeensyAudioSampler" "TeensyVariablePlayback" >/dev/null 2>&1 || true
for url in "${GIT_LIBS[@]}"; do
  echo "   $url"
  arduino-cli lib install --git-url "$url"
done
ok "GitHub libraries installed"

say "Patching ResamplingReader.h (prevents nullptr crashes)"
LIBDIR="$(arduino-cli config get directories.user)/libraries"
SRC="$REPO/_DOCS/ResamplingReader.h"
# folder name differs by install source (TeensyVariablePlayback vs teensy-variable-playback)
TARGET="$(find "$LIBDIR" -iname ResamplingReader.h -path '*variable*playback*src*' 2>/dev/null | head -n1)"
if [[ -f "$SRC" && -n "$TARGET" ]]; then
  cp -f "$SRC" "$TARGET"
  ok "patched $TARGET"
else
  warn "could not patch (src or target missing) — patch manually: see manual cap. 8.3"
fi

if [[ "$BUILD" == "1" ]]; then
  say "Compile-check (Teensy 4.1, USB = Serial + MIDIx16)"
  # arduino-cli requires the main .ino to match the sketch folder name, so we
  # compile a temp copy named soundpauli_ni404/ (the repo folder name differs).
  TMP="$(mktemp -d)/soundpauli_ni404"
  mkdir -p "$TMP"
  cp "$REPO"/*.ino "$REPO"/*.h "$TMP"/
  if arduino-cli compile -b "$FQBN" "$TMP"; then
    ok "COMPILE OK — firmware builds cleanly"
  else
    warn "compile failed — see the errors above"
    exit 1
  fi
  rm -rf "$(dirname "$TMP")"
fi

say "Done. Open soundpauli_ni404.ino in Arduino IDE and upload to your Teensy 4.1."
