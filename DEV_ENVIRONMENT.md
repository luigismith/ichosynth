[🇮🇹 Italiano](MANUALE_AMBIENTE.md) · **🇬🇧 English**

<div align="center">

# 💻 ichosynth — Development Environment

### Complete, up-to-date guide for Windows and macOS

Everything you need to compile, modify, and upload the firmware: from the IDE to the libraries, all the way to your first upload onto the Teensy 4.1.

[![Updated: June 2026](https://img.shields.io/badge/Updated-June%202026-2ea44f.svg)](#)
[![Arduino IDE 2.3.x](https://img.shields.io/badge/Arduino%20IDE-2.3.x-00979D.svg)](#)
[![Teensyduino 1.61](https://img.shields.io/badge/Teensyduino-1.61-ee6611.svg)](#)
[![OS: Windows · macOS](https://img.shields.io/badge/OS-Windows%20%C2%B7%20macOS-blue.svg)](#)

</div>

> ⚡ **In a hurry?** There's a **script that does everything for you** (Teensy core + libraries + patch +
> compile-check). Jump to [chapter 3](#3--the-fast-track-one-script-does-it-all). The manual guide is in the
> chapters that follow.

---

## 📑 Table of Contents

- [1 · What we install](#1--what-we-install)
- [2 · Requirements](#2--requirements)
- [3 · The fast track: one script does it all](#3--the-fast-track-one-script-does-it-all)
- [4 · Installing Arduino IDE](#4--installing-arduino-ide)
- [5 · Adding Teensy support](#5--adding-teensy-support)
- [6 · The libraries](#6--the-libraries)
- [7 · The mandatory step: ResamplingReader.h](#7--the-mandatory-step-resamplingreaderh)
- [8 · Downloading the project and compiling](#8--downloading-the-project-and-compiling)
- [9 · Optional tools (Python, Git)](#9--optional-tools-python-git)
- [10 · Checklist and common problems](#10--checklist-and-common-problems)

---

## 1 · What we install

| Component | Version | What it's for | Required |
|---|---|---|---|
| **Arduino IDE** | 2.3.x | writing/compiling the firmware | ✅ |
| **Teensy support** (Teensyduino) | 1.61 | adds the Teensy boards to the IDE (+ Teensy Loader) | ✅ |
| **Libraries** | see ch. 6 | FastLED **3.9.10**, TeensyPolyphony, etc. | ✅ |
| **ResamplingReader.h** (patch) | from the repo | avoids nullptr crashes during playback | ✅ |
| **Python** | 3.12 *(or 3.13+ with `audioop-lts`)* | `wavmaker` (sample conversion) | optional |
| **Git / GitHub CLI** | latest | cloning and version-controlling the project | optional |

> ⚠️ Two pitfalls that the guide (and the script) handle for you:
> 1. **FastLED must be 3.9.10** — the 3.10.x releases break on the Teensy's WS2812Serial path.
> 2. The two **newdigate** libraries (`teensy-variable-playback`, `teensy-polyphony`) must be taken from
>    **GitHub** (same HEAD): the copies in the Arduino registry are out of sync with each other.

---

## 2 · Requirements

- **Windows**: Windows 10 or 11, 64-bit. ⚠️ Do **not** use Arduino IDE from the **Microsoft Store**: it's
  incompatible with Teensy. Use the `.exe`/`.msi` installer (or winget).
- **macOS**: macOS 10.15 or later; native support for **Intel** and **Apple Silicon** (M1/M2/M3/M4). On
  macOS, **only** Arduino IDE 2.x is supported.
- **A micro-USB data cable** (not charge-only) for the Teensy 4.1.
- ~1 GB of disk space for the IDE + toolchain + libraries.

---

## 3 · The fast track: one script does it all

In the repo, under `scripts/`, there are two scripts that install the Teensy core + all the libraries with the
**correct versions**, apply the `ResamplingReader.h` patch, and run the **compile-check**.

First install **[`arduino-cli`](https://arduino.github.io/arduino-cli/)**, then run the script:

**Windows (PowerShell):**
```powershell
winget install ArduinoSA.CLI
powershell -ExecutionPolicy Bypass -File scripts\setup-dev-env.ps1
```

**macOS (Terminal):**
```bash
brew install arduino-cli
chmod +x scripts/setup-dev-env.sh
./scripts/setup-dev-env.sh
```

> 💡 If the script completes successfully, skip to [chapter 8.4](#84-compile-and-upload) for the upload. If
> you'd rather understand each step (or the script fails), continue with the manual guide below.

---

## 4 · Installing Arduino IDE

### Windows
**winget** (recommended): `winget install --id ArduinoSA.IDE --source winget`
or download the **Windows (.exe/.msi)** installer from `https://www.arduino.cc/en/software`.

> ⚠️ Mistake #1: **no Microsoft Store**. That version prevents the Teensy Loader from working.

### macOS
**Homebrew**: `brew install --cask arduino-ide`
or download the **.dmg** (universal Intel/Apple Silicon) and drag the app into Applications.

> ⚠️ **Gatekeeper**: on first launch use **right-click → Open** (once), or Settings →
> Privacy & Security → "Open Anyway".

---

## 5 · Adding Teensy support

1. Open Arduino IDE → **File → Preferences** (Windows, `Ctrl+,`) or **Arduino IDE → Settings** (macOS, `Cmd+,`).
2. In **"Additional boards manager URLs"** paste:
   ```text
   https://www.pjrc.com/teensy/package_teensy_index.json
   ```
3. Open the **Boards Manager** (icon on the left), search for **"teensy"** and install
   **"Teensy (for Arduino IDE 2.x.x)"** (1.61). The **Teensy Loader** will appear as well.

> ℹ️ **Drivers**: on Windows 10/11 and on macOS **no additional drivers are needed**.

Check: is **Tools → Board → Teensy → Teensy 4.1** present? You're ready.

---

## 6 · The libraries

Open the **Library Manager** (`Ctrl/Cmd+Shift+I`) and install:

| Search for | Notes |
|---|---|
| **FastLED** | ⚠️ exactly version **3.9.10** (not the latest) |
| **Mapf** | float mapping |
| **Switch** (by Albert van Dalen) | button/gesture handling (`avdweb_Switch`) |
| *(only if you use the OLED)* **Adafruit SSD1306** + **Adafruit GFX** | optional screen |

The two **newdigate** libraries are not installed from the Library Manager (the copies are out of sync): they
must be installed from GitHub. The easiest way is the **script** in [chapter 3](#3--the-fast-track-one-script-does-it-all);
alternatively, from `arduino-cli`:
```bash
arduino-cli config set library.enable_unsafe_install true
arduino-cli lib install --git-url https://github.com/newdigate/teensy-variable-playback.git
arduino-cli lib install --git-url https://github.com/newdigate/teensy-polyphony.git
```

> ℹ️ **Already included in the Teensy core** (don't install them separately): `Audio`, `Encoder`, `WS2812Serial`,
> `Wire`, `EEPROM`, `SD`.

---

## 7 · The mandatory step: ResamplingReader.h

The `teensy-variable-playback` library must be **patched** with the file provided in the repo
([`_DOCS/ResamplingReader.h`](_DOCS/ResamplingReader.h)), which prevents null-pointer crashes.

Replace the file at:
- **Windows**: `Documents\Arduino\libraries\teensy-variable-playback\src\ResamplingReader.h`
- **macOS**: `~/Documents/Arduino/libraries/teensy-variable-playback/src/ResamplingReader.h`

> ⚠️ This must be redone **every time you update** that library. (The script in ch. 3 does it for you.)

---

## 8 · Downloading the project and compiling

### 8.1 Download
```bash
git clone https://github.com/luigismith/ichosynth.git
```
or **Code → Download ZIP** from the GitHub page. Open `soundpauli_ni404.ino` with Arduino IDE.

### 8.2 Compile settings (Tools menu)
| Item | Value |
|---|---|
| **Board** | Teensy 4.1 |
| **USB Type** | **Serial + MIDIx16** |
| **CPU Speed** | 600 MHz (default) |
| **Port** | the Teensy's port (after connecting it) |

### 8.3 (3-encoder build) config.h
In [`config.h`](config.h) the 3-encoder build is **already set** (`HAS_ENCODER4 0`); leave it as is.
Optional fork features:
```c
#define OLED_ENABLED 1            // OLED status screen
#define MIDI_CLOCK_OUT_ENABLED 1  // MIDI clock out (master sync)
```

### 8.4 Compile and upload
1. Connect the Teensy 4.1 via USB (a **data** cable).
2. **Verify** (✓) to compile, then **Upload** (→).
3. The **Teensy Loader** opens: it usually programs on its own; if it stays waiting, press the
   **little white button** on the Teensy.
4. When the flash finishes, the animation starts on the LED matrix.

> 💡 The first compilation is slow (building the core); subsequent ones are fast.

---

## 9 · Optional tools (Python, Git)

### 9.1 Python — for the `wavmaker` sample converter
In the repo, under `_SDCARD/`, you'll find `wavmaker.exe` (Windows GUI, **no Python needed**) and the
`wavmaker_gui.py` / `wavmaker.py` sources.

> ⚠️ The Python script uses the `audioop` module, **removed in Python 3.13+**. Solutions:
> **(a)** use **Python 3.12**, or **(b)** `pip install audioop-lts`.

**Windows:** `winget install Python.Python.3.12`  · **macOS:** `brew install python@3.12`

### 9.2 Git and GitHub CLI
**Windows:** `winget install Git.Git` (+ `GitHub.cli` optional)
**macOS:** `xcode-select --install` (includes git) · `brew install gh` (optional)

---

## 10 · Checklist and common problems

| ✓ | Check |
|---|---|
| ☐ | Arduino IDE ≥ 2.3.x starts up |
| ☐ | Tools → Board → Teensy → Teensy 4.1 present |
| ☐ | The installed FastLED is **3.9.10** |
| ☐ | The two newdigate libraries installed from GitHub |
| ☐ | `ResamplingReader.h` replaced |
| ☐ | USB Type = Serial + MIDIx16 |
| ☐ | `soundpauli_ni404.ino` compiles without errors |

| Symptom | Cause / fix |
|---|---|
| Teensy doesn't appear in Boards Manager | URL not saved in Preferences; restart the IDE |
| "Teensy Loader is unable to…" (Windows) | you have the Microsoft Store IDE → use the official installer |
| `RGB_ORDER` / template errors in FastLED | FastLED isn't 3.9.10 (downgrade to 3.9.10) |
| `AudioPlaySdResmp` / `playRaw` / `override` errors | the newdigate libraries are the registry ones → install them from GitHub |
| `nullptr` / ResamplingReader errors | the patch from ch. 7 wasn't applied |
| `'usbMIDI' was not declared` | USB Type not set to Serial + MIDIx16 |
| macOS: "operation not permitted" on the libraries | re-grant access to Documents in Privacy & Security |
| Port not visible | charge-only USB cable → use a data cable |

---

<div align="center">

*Part of the **[ichosynth](README.md)** project · fork of NI404 (SP_) · for the ICHOS 2026 workshop.*

</div>
