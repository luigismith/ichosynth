#!/usr/bin/env python3
"""Build the REAL TŒRN firmware for our hand-soldered hardware (Teensy 4.1).

This compiles the unmodified TŒRN sketch against two drop-in replacement drivers
so it runs on cheap, hand-wired parts instead of the original's expensive ones:

  * 4x  Duppa I2C RGB encoders -> 4x KY-040 mechanical encoders  (i2cEncoderLibV2.h)
  * 3x  capacitive touch pads  -> 3x momentary tact switches      (FastTouch.h)
  * + an I2C OLED for the state TŒRN used to show via the encoder RGB rings.

The two drivers live in firmware/libraries/ and expose the exact API TŒRN calls, so
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
    python firmware/build_toern.py            # build -> firmware/build/toern.hex
    python firmware/build_toern.py --flash     # build, then flash with teensy_loader_cli if found

Requires: arduino-cli on PATH, the teensy:avr core (>=1.61.0) installed, and the
TŒRN sources under emulator/toern-src/ (cloned automatically if missing).
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOERN_SRC = os.path.join(REPO, "emulator", "toern-src")
TOERN_REPO_URL = "https://github.com/soundpauli/toern.git"
TOERN_COMMIT = "98f13dacf7ffa4f086d85244ce9abb12ea8c480e"   # "final bugfixes for 2.2", 2026-05-21
TOERN_INO_SHA1 = "159e135b369473a24a615c3aa6f50e84247f58f7"  # toern.ino at that commit, LF-normalised
LIBRARIES = os.path.join(REPO, "firmware", "libraries")
OLED_LIB = os.path.join(LIBRARIES, "IchosOled", "IchosOled.h")
OUT_DIR = os.path.join(REPO, "firmware", "build")
FQBN = "teensy:avr:teensy41:usb=serialmidi16,opt=o1std"

# SWITCH_1/2/3 -> our three tact switches (must match ICHOS_BTN_PINS in FastTouch.h).
PIN_REMAP = {"SWITCH_1": 25, "SWITCH_2": 26, "SWITCH_3": 28}

# Feature trims requested for the ichosynth build (lighten / simplify the upstream
# TŒRN firmware). Applied as build-time source patches so emulator/toern-src stays
# pristine. See docs/reference/FEATURE_INVENTORY.md.
REMOVE_2ND_LED_STRIP = True   # drop the optional reactive 256-LED strip (frees pin 24)


def run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, **kw)


def find_arduino_cli():
    """arduino-cli on PATH, else the usual per-user install location (~/bin)."""
    exe = shutil.which("arduino-cli")
    if exe:
        return exe
    for cand in ("~/bin/arduino-cli.exe", "~/bin/arduino-cli"):
        cand = os.path.expanduser(cand)
        if os.path.isfile(cand):
            return cand
    return None


def core_library(cli, name):
    """Path of a library bundled with the newest installed teensy:avr core.

    The sketchbook may hold a newer, incompatible copy (FastLED 3.10 no longer compiles
    TŒRN's FastLED.addLeds<WS2812SERIAL, ...>), and arduino-cli prefers sketchbook
    libraries over platform ones. Passing the core's copy with --library pins it, so
    the build does not depend on what else is installed on the machine.
    """
    r = subprocess.run([cli, "config", "get", "directories.data"], capture_output=True, text=True)
    root = os.path.join(r.stdout.strip(), "packages", "teensy", "hardware", "avr")
    if not os.path.isdir(root):
        return None
    def ver(v):
        return tuple(int(x) for x in re.findall(r"\d+", v))
    for v in sorted(os.listdir(root), key=ver, reverse=True):
        path = os.path.join(root, v, "libraries", name)
        if os.path.isdir(path):
            return path
    return None


def ensure_sources():
    """TŒRN sources at the pinned upstream commit (cloned if missing).

    Upstream keeps moving; our shims and patches were checked against TOERN_COMMIT, so
    a fresh checkout is pinned there instead of following HEAD.
    """
    if not os.path.isfile(os.path.join(TOERN_SRC, "toern.ino")):
        print(f"TŒRN sources not found at {TOERN_SRC} -> cloning {TOERN_REPO_URL} @ {TOERN_COMMIT[:10]}")
        os.makedirs(os.path.dirname(TOERN_SRC), exist_ok=True)
        r = run(["git", "clone", TOERN_REPO_URL, TOERN_SRC])
        if r.returncode == 0:
            r = run(["git", "-C", TOERN_SRC, "checkout", "-q", TOERN_COMMIT])
        if r.returncode != 0:
            sys.exit(f"Could not get TŒRN {TOERN_COMMIT}. Clone {TOERN_REPO_URL} into emulator/toern-src/ "
                     f"and check out that commit.")
    with open(os.path.join(TOERN_SRC, "toern.ino"), "rb") as f:
        digest = hashlib.sha1(f.read().replace(b"\r\n", b"\n")).hexdigest()
    if digest != TOERN_INO_SHA1:
        print(f"  WARNING: emulator/toern-src/toern.ino is not the pinned TŒRN {TOERN_COMMIT[:10]} "
              f"(sha1 {digest[:10]}): the patches below will still refuse to apply if anything moved.")


def patch_behaviour(sketch):
    """Hardware-behaviour patches for our build (each one must apply, or the build stops).

    - SWITCH_1/2/3 are tact switches to GND, not touch pads: INPUT_PULLUP, not PULLDOWN
      (with PULLDOWN an open button reads "pressed" and TŒRN hangs in INIT MODE at boot).
    - Pin 2 (fast-record contact, active LOW) gets a pull-up so it can't float.
    - The SD card is the Teensy 4.1's built-in slot (SDIO), not the Audio Adaptor's SPI
      slot on pin 10.
    - The default recording input is LINE IN (our build has a Line In jack, no mic).
    """
    ino = os.path.join(sketch, "toern.ino")
    with open(ino, "r", encoding="utf-8", errors="surrogateescape") as f:
        text = f.read()
    text, a = re.subn(r"pinMode\((SWITCH_[123]),\s*INPUT_PULLDOWN\)", r"pinMode(\1, INPUT_PULLUP)", text)
    text, b = re.subn(r"(pinMode\(SWITCH_3,\s*INPUT_PULLUP\);[^\n]*\n)",
                      r"\1  pinMode(2, INPUT_PULLUP);  // ichosynth: fast-record contact, active LOW\n",
                      text, count=1)
    text, c = re.subn(r"#define\s+INT_SD\s+10\b", "#define INT_SD BUILTIN_SDCARD  // ichosynth: Teensy 4.1 slot",
                      text, count=1)
    text, d = re.subn(r"recMode = 1;(\s*)// default: MIC", r"recMode = -1;\1// ichosynth default: LINE IN",
                      text, count=1)
    if (a, b, c, d) != (3, 1, 1, 1):
        sys.exit(f"Could not apply behaviour patches (pullups={a}, pin2={b}, sd={c}, recIn={d}).")
    with open(ino, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(text)
    print("  buttons INPUT_PULLUP + pin 2 pull-up, SD = built-in slot, record input = LINE IN")


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

    The HUD lives in its own library (firmware/libraries/IchosOled) so its graphics
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

    cli = find_arduino_cli()
    if not cli:
        sys.exit("arduino-cli not found (PATH or ~/bin). Install it and the teensy:avr core first.")
    fastled = core_library(cli, "FastLED")
    if not fastled:
        sys.exit("FastLED bundled with the teensy:avr core not found. Install the teensy:avr core (>=1.61.0).")
    ensure_sources()

    build_root = tempfile.mkdtemp(prefix="toernbuild_")
    try:
        print("Staging TŒRN sources ...")
        sketch = stage(build_root)
        patch_pins(sketch)
        patch_behaviour(sketch)
        remove_features(sketch)
        add_oled_hud(sketch)

        os.makedirs(OUT_DIR, exist_ok=True)
        print(f"Compiling for {FQBN} ...")
        print(f"  FastLED pinned to the core's copy: {fastled}")
        r = run([cli, "compile", "-b", FQBN, sketch, "--libraries", LIBRARIES,
                 "--library", fastled, "--output-dir", OUT_DIR])
        if r.returncode != 0:
            sys.exit("Compile failed. See output above.")

        # arduino-cli writes "<sketch>.ino.hex"; copy it to a stable name.
        built = os.path.join(OUT_DIR, "toern.ino.hex")
        final = os.path.join(OUT_DIR, "toern.hex")
        if not os.path.isfile(built):
            sys.exit(f"Compile reported success but {built} is missing.")
        try:
            shutil.copyfile(built, final)
        except OSError:
            final = built  # dest locked (e.g. open elsewhere); the .ino.hex is valid
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
