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
     collide with our right-hand KY-040 (CLK=4, DT=2, SW=3).  We remap them to the
     three tact-switch pins 24/25/26 (matching ICHOS_BTN_PINS in FastTouch.h).

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
OUT_DIR = os.path.join(REPO, "teensy", "firmware")
FQBN = "teensy:avr:teensy41:usb=serialmidi16,opt=o1std"

# SWITCH_1/2/3 -> our three tact switches (must match ICHOS_BTN_PINS in FastTouch.h).
PIN_REMAP = {"SWITCH_1": 24, "SWITCH_2": 25, "SWITCH_3": 26}


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

        os.makedirs(OUT_DIR, exist_ok=True)
        print(f"Compiling for {FQBN} ...")
        r = run(["arduino-cli", "compile", "-b", FQBN, sketch,
                 "--libraries", LIBRARIES, "--output-dir", OUT_DIR])
        if r.returncode != 0:
            sys.exit("Compile failed. See output above.")

        hexes = [f for f in os.listdir(OUT_DIR) if f.endswith(".hex")]
        final = os.path.join(OUT_DIR, "toern.hex")
        if hexes:
            shutil.copy2(os.path.join(OUT_DIR, hexes[0]), final)
            print(f"\nFirmware ready: {final}")

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
