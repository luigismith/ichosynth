#!/usr/bin/env python3
"""Build (if needed) and launch the ichosynth emulator.

Two firmwares can run in the emulator:
  * product  (default) -> toernemu: the real ichosynth firmware. The CMake step stages
                          and patches the pinned TŒRN sketch with
                          firmware/build_toern.py --stage-only — the same staging and
                          patches the Teensy build uses — and compiles it with the real
                          hardware drivers from firmware/libraries/ (KY-040 encoders,
                          tact switches, the IchosOled HUD) on top of desktop models of
                          the Teensy core: GPIO with pull-ups, an I2C bus with an SSD1306,
                          the SD card, EEPROM, timers and the Teensy Audio Library. Same
                          sources and drivers as the flashed .hex, not the same machine
                          code: timing and DSP are close, not cycle-accurate (MANUALE §12).
  * bench    (--bench) -> ni404emu: the legacy NI404-based firmware
                          (legacy/soundpauli_ni404/), kept as a fallback/reference.

Usage:
    python emulator/run.py                # build (if needed) + launch the product firmware
    python emulator/run.py --bench        # build + launch the NI404 fallback
    python emulator/run.py --rebuild      # wipe the build folder and rebuild from scratch
    python emulator/run.py --build-only   # build but do not launch
    python emulator/run.py -- --no-sd     # anything after "--" goes to the emulator
    python emulator/run.py -- --hwtest    # e.g. the headless hardware-behaviour test

The build runs at below-normal priority (the PC stays usable). On Windows it finds the
MSYS2/MinGW64 toolchain (C:\\msys64\\mingw64\\bin) and copies SDL2.dll next to the exe.
The TŒRN sources are cloned into emulator/toern-src at the commit pinned in
firmware/build_toern.py if they are missing.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys

EMU = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(EMU)
BUILD = os.path.join(EMU, "build")
MSYS_BIN = r"C:\msys64\mingw64\bin"
BELOW_NORMAL = 0x00004000          # Windows BELOW_NORMAL_PRIORITY_CLASS


def toolchain_env():
    """Return an environment with the MinGW64 toolchain on PATH (Windows)."""
    env = dict(os.environ)
    if os.name == "nt" and os.path.isdir(MSYS_BIN):
        env["PATH"] = MSYS_BIN + os.pathsep + env.get("PATH", "")
    return env


def which(tool, env):
    return shutil.which(tool, path=env.get("PATH"))


def run(cmd, env, low_priority=False):
    # On Windows, CreateProcess resolves the exe against the *parent* PATH, not the
    # env we pass, so resolve cmd[0] explicitly against the toolchain PATH.
    exe = which(cmd[0], env) or cmd[0]
    print("  $", " ".join(cmd))
    kw = {}
    if low_priority:
        if os.name == "nt":
            kw["creationflags"] = BELOW_NORMAL
        else:
            kw["preexec_fn"] = lambda: os.nice(10)
    return subprocess.run([exe] + cmd[1:], cwd=EMU, env=env, **kw)


def load_build_toern():
    """firmware/build_toern.py as a module: the one place the TŒRN commit is pinned."""
    path = os.path.join(REPO, "firmware", "build_toern.py")
    spec = importlib.util.spec_from_file_location("build_toern", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_sdl2(env):
    """Where SDL2 is, or None. Windows: the MSYS2 package; elsewhere sdl2-config/pkg-config."""
    if os.name == "nt":
        for d in env.get("PATH", "").split(os.pathsep):
            if d and os.path.isfile(os.path.join(d, "SDL2.dll")) and \
                    os.path.isdir(os.path.join(os.path.dirname(d), "lib", "cmake", "SDL2")):
                return os.path.join(d, "SDL2.dll")
        return None
    for probe in (["sdl2-config", "--version"], ["pkg-config", "--modversion", "sdl2"]):
        if which(probe[0], env):
            r = subprocess.run(probe, capture_output=True, text=True, env=env)
            if r.returncode == 0:
                return probe[0]
    return None


def check_tools(env, need_make):
    missing = []
    if not which("cmake", env):
        missing.append("cmake")
    if not (which("g++", env) or which("c++", env)):
        missing.append("a C++ compiler (g++)")
    if need_make and not which("mingw32-make", env):
        missing.append("mingw32-make")
    if missing:
        hint = ("install MSYS2 (https://www.msys2.org) into C:\\msys64, then run "
                "emulator/scripts/bootstrap-windows.ps1 (it installs gcc, cmake, make, SDL2)"
                if os.name == "nt" else
                "macOS: emulator/scripts/bootstrap-macos.sh (Homebrew gcc, cmake, sdl2); "
                "Linux: install gcc/g++, cmake and the SDL2 development package")
        sys.exit("Missing: " + ", ".join(missing) + ".\n  -> " + hint)
    if not find_sdl2(env):
        sys.exit("SDL2 (development files) not found.\n  -> " + (
            "in an MSYS2 shell: pacman -S mingw-w64-x86_64-SDL2" if os.name == "nt" else
            "macOS: brew install sdl2; Linux: install libsdl2-dev (or SDL2-devel)"))


def main():
    ap = argparse.ArgumentParser(description="Build and launch the ichosynth emulator.",
                                 epilog="Arguments after '--' are passed to the emulator.")
    ap.add_argument("--bench", action="store_true",
                    help="run the NI404 fallback firmware instead of the product (TŒRN)")
    ap.add_argument("--rebuild", action="store_true", help="wipe the build dir first")
    ap.add_argument("--build-only", action="store_true", help="build but do not launch")
    argv = sys.argv[1:]
    passthrough = []
    if "--" in argv:
        i = argv.index("--")
        argv, passthrough = argv[:i], argv[i + 1:]
    args = ap.parse_args(argv)

    product = not args.bench
    target = "toernemu" if product else "ni404emu"
    env = toolchain_env()
    check_tools(env, need_make=(os.name == "nt"))

    if product:
        bt = load_build_toern()
        bt.ensure_sources()       # clones soundpauli/toern at the pinned commit if missing (needs git)

    if args.rebuild and os.path.isdir(BUILD):
        shutil.rmtree(BUILD, ignore_errors=True)

    # Configure only when there is no build tree yet: CMake re-runs by itself when
    # CMakeLists.txt, build_toern.py or the TŒRN sources change. Both targets are
    # always configured (no option flipping between runs, so no needless rebuilds).
    if not os.path.isfile(os.path.join(BUILD, "CMakeCache.txt")):
        cfg = ["cmake", "-S", EMU, "-B", BUILD, "-DCMAKE_BUILD_TYPE=Release",
               "-DEMU_BUILD_TOERN=ON", "-DPython3_EXECUTABLE=" + sys.executable]
        if os.name == "nt":
            cfg += ["-G", "MinGW Makefiles"]
        if run(cfg, env, low_priority=True).returncode != 0:
            sys.exit("CMake configure failed (see above).")

    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    if run(["cmake", "--build", BUILD, "--target", target, "-j", jobs], env, low_priority=True).returncode != 0:
        sys.exit("Build failed (see above).")

    exe = os.path.join(BUILD, target + (".exe" if os.name == "nt" else ""))
    if not os.path.isfile(exe):
        sys.exit(f"Built, but {exe} not found (is the TŒRN source in emulator/toern-src?).")
    if os.name == "nt":
        dll = find_sdl2(env)
        dst = os.path.join(BUILD, "SDL2.dll")
        if dll and (not os.path.isfile(dst) or os.path.getmtime(dst) < os.path.getmtime(dll)):
            shutil.copy2(dll, dst)   # so the exe also starts by double-click
    print(f"\n{'Product (TŒRN)' if product else 'Bench (NI404)'} emulator: {exe}")
    if args.build_only:
        return
    headless = any(a.startswith("--") and a not in ("--no-sd", "--demo", "--midi") for a in passthrough)
    if headless:
        # Headless modes (--hwtest, --selftest, ...): wait and return their exit code.
        # Hand the std handles over explicitly: a Windows GUI-subsystem exe does not
        # inherit them otherwise, and its report would be lost.
        sys.stdout.flush()
        r = subprocess.run([exe] + passthrough, cwd=BUILD, env=env,
                           stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr)
        sys.exit(r.returncode)
    print("Launching… (close the window to exit)")
    subprocess.Popen([exe] + passthrough, cwd=BUILD, env=env)


if __name__ == "__main__":
    main()
