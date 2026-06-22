#!/usr/bin/env python3
"""Build the REAL TŒRN firmware for our hand-soldered hardware (Teensy 4.1).

This compiles the unmodified TŒRN sketch against two drop-in replacement drivers
so it runs on cheap, hand-wired parts instead of the original's expensive ones:

  * 4x  Duppa I2C RGB encoders -> 4x KY-040 mechanical encoders  (i2cEncoderLibV2.h)
  * 3x  capacitive touch pads  -> 3x momentary tact switches      (FastTouch.h)
  * + an I2C OLED for the state TŒRN used to show via the encoder RGB rings.

The two drivers live in teensy/libraries/ and expose the exact API TŒRN calls, so
the firmware itself is compiled UNCHANGED except for one pin remap (below).

Two things this script takes care of that a naive `arduino-cli compile` does not:

  1. opt=o1std (-O1).  At the default -O2 the Teensy gcc CRASHES (exit 0xffffffff,
     an internal-compiler-error / OOM) on TŒRN's ~23k-line single translation unit.
     -O1 builds cleanly and the result still fits with room to spare.

  2. SWITCH_1/2/3 pin remap.  TŒRN's touch switches default to pins 2/3/4, which
     clash with TŒRN's own hard-coded use of those pins; we remap them to the three
     tact-switch pins 25/26/28 (matching ICHOS_BTN_PINS in FastTouch.h). The encoders
     likewise avoid TŒRN's reserved GPIO (E4 = 37/38/39, not the default 4/2/3).

Usage:
    python teensy/build_toern.py            # build -> teensy/firmware/toern.hex
    python teensy/build_toern.py --flash     # build, then flash with teensy_loader_cli if found

Requires: arduino-cli on PATH, the teensy:avr core (>=1.61.0) installed, and the
TŒRN sources under emulator/toern-src/ (cloned automatically if missing).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOERN_SRC = os.path.join(REPO, "emulator", "toern-src")
TOERN_REPO_URL = "https://github.com/soundpauli/toern.git"
LIBRARIES = os.path.join(REPO, "teensy", "libraries")
OLED_LIB = os.path.join(LIBRARIES, "IchosOled", "IchosOled.h")
OUT_DIR = os.path.join(REPO, "teensy", "firmware")
FQBN = "teensy:avr:teensy41:usb=serialmidi16,opt=o1std"

# SWITCH_1/2/3 -> our three tact switches (must match ICHOS_BTN_PINS in FastTouch.h).
PIN_REMAP = {"SWITCH_1": 25, "SWITCH_2": 26, "SWITCH_3": 28}

# Feature trims requested for the ichosynth build (lighten / simplify the upstream
# TŒRN firmware). Applied as build-time source patches so emulator/toern-src stays
# pristine. See _DOCS/FEATURE_INVENTORY.md.
REMOVE_2ND_LED_STRIP = True   # drop the optional reactive 256-LED strip (frees pin 24)


def run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, **kw)


def ensure_sources():
    if os.path.isfile(os.path.join(TOERN_SRC, "toern.ino")):
        return
    print(f"TŒRN sources not found at {TOERN_SRC} -> cloning {TOERN_REPO_URL}")
    os.makedirs(os.path.dirname(TOERN_SRC), exist_ok=True)
    r = run(["git", "clone", "--depth", "1", TOERN_REPO_URL, TOERN_SRC])
    if r.returncode != 0:
        sys.exit("Could not clone TŒRN sources. Clone it manually into emulator/toern-src/.")


def stage(build_root):
    sketch = os.path.join(build_root, "toern")
    os.makedirs(os.path.join(sketch, "src"), exist_ok=True)
    for name in os.listdir(TOERN_SRC):
        if name.endswith((".ino", ".h")):
            shutil.copy2(os.path.join(TOERN_SRC, name), sketch)
    src = os.path.join(TOERN_SRC, "src")
    if os.path.isdir(src):
        for name in os.listdir(src):
            shutil.copy2(os.path.join(src, name), os.path.join(sketch, "src"))
    return sketch


def patch_pins(sketch):
    ino = os.path.join(sketch, "toern.ino")
    with open(ino, "r", encoding="utf-8", errors="surrogateescape") as f:
        text = f.read()
    for name, pin in PIN_REMAP.items():
        text, n = re.subn(rf"(#define\s+{name}\s+)\d+", rf"\g<1>{pin}", text, count=1)
        if not n:
            sys.exit(f"Could not find #define {name} to remap in toern.ino")
    with open(ino, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(text)
    print("  pins remapped:", ", ".join(f"{k}={v}" for k, v in PIN_REMAP.items()))


def remove_features(sketch):
    """Apply the requested feature trims as targeted source patches."""
    if REMOVE_2ND_LED_STRIP:
        ino = os.path.join(sketch, "toern.ino")
        with open(ino, "r", encoding="utf-8", errors="surrogateescape") as f:
            text = f.read()
        # Stop driving the 2nd strip on pin 24 (frees the pin for other use).
        text, a = re.subn(r"^[ \t]*FastLED\.addLeds<WS2812SERIAL,\s*24,[^\n]*\n",
                          "  // 2nd LED strip removed (ichosynth port): pin 24 freed\n",
                          text, count=1, flags=re.M)
        with open(ino, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(text)
        # Skip the per-frame strip update (saves CPU); buffer stays but is never shown.
        leds = os.path.join(sketch, "toern_leds.ino")
        with open(leds, "r", encoding="utf-8", errors="surrogateescape") as f:
            ltext = f.read()
        ltext, b = re.subn(r"(void updateLedStrip\(\)\s*\{)",
                           r"\1\n  return;  // 2nd LED strip removed (ichosynth port)",
                           ltext, count=1)
        with open(leds, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(ltext)
        if not (a and b):
            sys.exit(f"Could not remove 2nd LED strip (addLeds={a}, update={b}).")
        print("  feature removed: 2nd LED strip (pin 24 freed)")


def add_oled_hud(sketch):
    """Wire the IchosOled library HUD into the sketch.

    The HUD lives in its own library (teensy/libraries/IchosOled) so its graphics
    code compiles as a separate translation unit — adding it to TŒRN's giant single
    TU crashes the Teensy gcc. Here we only inject a lightweight include, the begin()
    call, and a one-line glue in loop() that reads TŒRN's globals and renders.
    """
    if not os.path.isfile(OLED_LIB):
        print("  (no OLED HUD library found, skipping)")
        return
    ino = os.path.join(sketch, "toern.ino")
    with open(ino, "r", encoding="utf-8", errors="surrogateescape") as f:
        text = f.read()
    # Lightweight include (no graphics headers) right after the FastTouch include.
    text, n0 = re.subn(r"(#include <FastTouch.h>)",
                       r"\1\n#include <IchosOled.h>", text, count=1)
    # begin() at the end of setup() (codec + Wire are up by then).
    text, n1 = re.subn(r"(\n[ \t]*// END SETUP\b)",
                       r"\n  ichosOledBegin();\1", text, count=1)
    # One-line glue in loop(): read globals and refresh the HUD (self-throttled).
    glue = ("\n  if (currentMode) ichosOledRender((int)GLOB.currentChannel, "
            "(int)GLOB.vol, (int)(SMP.bpm + 0.5f), (int)GLOB.page, "
            "currentMode->name.c_str(), isNowPlaying, isRecording);")
    text, n2 = re.subn(r"(void loop\(\)\s*\{)", r"\1" + glue, text, count=1)
    if not (n0 and n1 and n2):
        sys.exit(f"Could not inject OLED HUD (include={n0}, begin={n1}, loop={n2}).")
    with open(ino, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(text)
    print("  OLED HUD wired in (IchosOled library: include + begin + loop glue)")


def main():
    ap = argparse.ArgumentParser(description="Build the real TŒRN firmware for our Teensy 4.1.")
    ap.add_argument("--flash", action="store_true", help="flash after building (teensy_loader_cli)")
    ap.add_argument("--keep", action="store_true", help="keep the temporary build folder")
    args = ap.parse_args()

    if not shutil.which("arduino-cli"):
        sys.exit("arduino-cli not on PATH. Install it and the teensy:avr core first.")
    ensure_sources()

    build_root = tempfile.mkdtemp(prefix="toernbuild_")
    try:
        print("Staging TŒRN sources ...")
        sketch = stage(build_root)
        patch_pins(sketch)
        remove_features(sketch)
        add_oled_hud(sketch)

        os.makedirs(OUT_DIR, exist_ok=True)
        print(f"Compiling for {FQBN} ...")
        r = run(["arduino-cli", "compile", "-b", FQBN, sketch,
                 "--libraries", LIBRARIES, "--output-dir", OUT_DIR])
        if r.returncode != 0:
            sys.exit("Compile failed. See output above.")

        # arduino-cli writes "<sketch>.ino.hex"; copy it to a stable name.
        built = os.path.join(OUT_DIR, "toern.ino.hex")
        final = os.path.join(OUT_DIR, "toern.hex")
        if os.path.isfile(built):
            try:
                shutil.copyfile(built, final)
                out = final
            except OSError:
                out = built  # dest locked (e.g. open elsewhere); the .ino.hex is valid
            print(f"\nFirmware ready: {out}")

        if args.flash:
            loader = shutil.which("teensy_loader_cli")
            if not loader:
                print("teensy_loader_cli not found; flash manually with the GUI flasher.")
            else:
                run([loader, "--mcu=TEENSY41", "-w", "-v", final])
    finally:
        if not args.keep:
            shutil.rmtree(build_root, ignore_errors=True)


if __name__ == "__main__":
    main()
