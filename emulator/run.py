#!/usr/bin/env python3
"""Launch the ichosynth emulator with the firmware you want to test.

The emulator runs the very same firmware the physical instrument runs, on the same
modelled hardware (4 encoders + 3 buttons + OLED, 16x16 grid, audio). Use it to try
variations of the synth on your desk before flashing the Teensy.

Two firmwares can run in the emulator:
  * product  (default) -> the REAL TŒRN firmware (emulator/toern-src), i.e. exactly
                          what teensy/build_toern.py flashes to the instrument.
  * bench    (--bench) -> the NI404-based hybrid (../soundpauli_ni404.ino), the
                          fallback/reference firmware.

Usage:
    python emulator/run.py                # build (if needed) + launch the product firmware
    python emulator/run.py --bench        # build + launch the NI404 fallback
    python emulator/run.py --rebuild      # force a clean reconfigure/build first
    python emulator/run.py --build-only   # build but do not launch

It finds the MSYS2/MinGW64 toolchain automatically on Windows (C:\\msys64\\mingw64\\bin)
and clones the TŒRN sources into emulator/toern-src if they are missing.
"""
import argparse
import os
import shutil
import subprocess
import sys

EMU = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(EMU, "build")
TOERN_SRC = os.path.join(EMU, "toern-src")
TOERN_REPO_URL = "https://github.com/soundpauli/toern.git"
MSYS_BIN = r"C:\msys64\mingw64\bin"


def toolchain_env():
    """Return an environment with the MinGW64 toolchain on PATH (Windows)."""
    env = dict(os.environ)
    if os.name == "nt" and os.path.isdir(MSYS_BIN):
        env["PATH"] = MSYS_BIN + os.pathsep + env.get("PATH", "")
    return env


def have(tool, env):
    return shutil.which(tool, path=env.get("PATH")) is not None


def run(cmd, env):
    # On Windows, CreateProcess resolves the exe against the *parent* PATH, not the
    # env we pass, so resolve cmd[0] explicitly against the toolchain PATH.
    exe = shutil.which(cmd[0], path=env.get("PATH")) or cmd[0]
    print("  $", " ".join(cmd))
    return subprocess.run([exe] + cmd[1:], cwd=EMU, env=env)


def ensure_toern_sources(env):
    if os.path.isfile(os.path.join(TOERN_SRC, "toern.ino")):
        return
    print(f"TŒRN sources not found -> cloning {TOERN_REPO_URL}")
    if run(["git", "clone", "--depth", "1", TOERN_REPO_URL, TOERN_SRC], env).returncode != 0:
        sys.exit("Could not clone TŒRN sources. Clone it manually into emulator/toern-src/.")


def main():
    ap = argparse.ArgumentParser(description="Launch the ichosynth emulator.")
    ap.add_argument("--bench", action="store_true",
                    help="run the NI404 fallback firmware instead of the product (TŒRN)")
    ap.add_argument("--rebuild", action="store_true", help="wipe the build dir first")
    ap.add_argument("--build-only", action="store_true", help="build but do not launch")
    args = ap.parse_args()

    product = not args.bench
    target = "toernemu" if product else "ni404emu"
    env = toolchain_env()

    if not have("cmake", env) or not (have("g++", env) or have("c++", env)):
        sys.exit("Could not find cmake + a C++ compiler. Install MSYS2 MinGW64 "
                 "(C:\\msys64) or put the toolchain on PATH.")
    if product:
        ensure_toern_sources(env)

    if args.rebuild and os.path.isdir(BUILD):
        shutil.rmtree(BUILD, ignore_errors=True)

    # Configure (enable the TŒRN target when building the product firmware).
    cfg = ["cmake", "-S", EMU, "-B", BUILD]
    if os.name == "nt":
        cfg += ["-G", "MinGW Makefiles"]
    cfg += ["-DEMU_BUILD_TOERN_REF=" + ("ON" if product else "OFF")]
    if run(cfg, env).returncode != 0:
        sys.exit("CMake configure failed.")

    if run(["cmake", "--build", BUILD, "--target", target, "-j", "6"], env).returncode != 0:
        sys.exit("Build failed.")

    exe = os.path.join(BUILD, target + (".exe" if os.name == "nt" else ""))
    if not os.path.isfile(exe):
        sys.exit(f"Built, but {exe} not found.")
    print(f"\n{'Product (TŒRN)' if product else 'Bench (NI404)'} emulator: {exe}")
    if args.build_only:
        return
    print("Launching… (close the window to exit)")
    subprocess.Popen([exe], cwd=EMU, env=env)


if __name__ == "__main__":
    main()
