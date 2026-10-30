# TŒRN on hand-soldered hardware — the port

This folder builds the **real [TŒRN](https://github.com/soundpauli/toern) firmware**
(by soundpauli, MIT) for our hand-wired instrument: a Teensy 4.1 + Teensy Audio
Board + 16×16 WS2812 matrix + **4 KY-040 encoders + 3 tact switches + 1 I²C OLED**,
**no PCB**. TŒRN is already a Teensy 4.1 instrument, so all of its DSP, sequencer
and sampler features come across unchanged — we only replace the expensive input
parts with cheap, solderable ones.

## What gets replaced (and how)

| TŒRN original | Our hardware | How |
|---|---|---|
| 4× Duppa I²C RGB encoders | 4× **KY-040** mechanical encoders (turn + push) | `libraries/i2cEncoderLibV2.h` — a drop-in re-implementation of the Duppa API on top of the `Encoder` library + a push pin |
| 3× capacitive touch pads | 3× **tact switches** (HUAZIZ 4-pin kit) | `libraries/FastTouch.h` — `fastTouchRead(pin)` reads a button (INPUT_PULLUP, active-low) and returns a value over TŒRN's touch threshold |
| encoder RGB-ring feedback | **I²C OLED** (state shown as text) | `libraries/IchosOled/` — a tiny FLASHMEM SSD1306 driver showing channel / mode / transport / BPM / volume / page. `build_toern.py` injects its `begin()`/`render()` calls |

The firmware source itself is compiled **unchanged** except for one pin remap
(below). The two drivers expose the exact API names/constants TŒRN calls
(`i2cEncoderLibV2::DIRE_LEFT`, `writeRGBCode`, `updateStatus`, …), so the sketch
links against them with no edits.

## Pin map

KY-040 encoders, `{CLK, DT, SW}`, left → right (override via `ICHOS_ENC_PINS`):

| Encoder | CLK | DT | SW |
|---|---|---|---|
| E1 (left) | 5 | 22 | 15 |
| E2 | 32 | 33 | 41 |
| E3 | 9 | 14 | 16 |
| E4 (right) | 37 | 38 | 39 |

Tact switches (`ICHOS_BTN_PINS`, other side to GND, active-low): **25, 26, 28**.

> **Pin map is collision-free with TŒRN's hard-coded GPIO and the Audio Shield.**
> TŒRN hard-codes pins 2/3/4 (touch switches + a pin-4 output + a pin-2 read), 17
> (matrix), 24 (an optional 2nd LED strip, removed in this build), 27 (INT), 30/36
> (LED power), 40 (battery ADC); the Audio Shield reserves 6/7/8/10-13/18-21/23. The
> encoders and buttons above avoid all of these. `build_toern.py` remaps TŒRN's
> `SWITCH_1/2/3` (pins 2/3/4) to **25/26/28** to match `ICHOS_BTN_PINS`. The TTP223
> external-touch path (pins 5/22) is off by default (`exttouch=false`), so E1 is free.

## Building

```sh
python teensy/build_toern.py            # -> teensy/firmware/toern.hex
python teensy/build_toern.py --flash    # build, then flash (teensy_loader_cli)
```

Needs `arduino-cli` (on PATH or in `~/bin`) and the `teensy:avr` core (≥ 1.61.0). The
TŒRN sources are expected under `emulator/toern-src/`; if missing, the script clones them
**pinned to upstream commit `98f13da`** ("final bugfixes for 2.2") — the commit the shims
and patches were checked against — and warns if the local `toern.ino` differs from it.

The build is reproducible on any machine:
- **FastLED is pinned to the copy bundled with the teensy:avr core** (passed with
  `--library`). A newer FastLED in the Arduino sketchbook (3.10.x) no longer compiles TŒRN's
  `FastLED.addLeds<WS2812SERIAL, …>` and would otherwise win over the core's copy.
- Every source patch must apply, or the build stops with an error.

### Hardware-behaviour patches

Applied to a staged copy (the vendored sources stay pristine):

| Patch | Why |
|---|---|
| `SWITCH_1/2/3` → pins 25/26/28 | the stock 2/3/4 collide with E4's original pins |
| `pinMode(SWITCH_n, INPUT_PULLDOWN)` → `INPUT_PULLUP` | right for touch pads, wrong for buttons to GND: an open button would read "pressed" and TŒRN would hang in INIT MODE at boot |
| `pinMode(2, INPUT_PULLUP)` | pin 2 is TŒRN's fast-record contact (active LOW); unwired it would float |
| `INT_SD 10` → `BUILTIN_SDCARD` | the SD card is the Teensy 4.1's own slot (SDIO), not the audio board's |
| default record input MIC → LINE IN | our build has a Line In jack and no mic |
| 2nd LED strip removed | frees pin 24 |
| OLED HUD glue | `ichosOledBegin()` + `ichosOledRender(…)` |

The drivers also guard against the same problems on their own: `FastTouch` re-asserts the
pull-up on every read, waits for it to settle before the first sample (TŒRN checks SWITCH_1
for "CLR RAM", which erases the EEPROM) and debounces; `i2cEncoderLibV2` debounces the
push switch, creates each `Encoder` only once (TŒRN re-calls `begin()` on E1) and returns
Duppa-style status from `readStatus()` without side effects.

### Why `opt=o1std` (-O1) and not the default

At the default `-O2` the Teensy gcc **crashes** compiling TŒRN's ~23k-line single
translation unit — it exits `0xffffffff` (an internal-compiler-error / out-of-memory)
with no source error. `-O1` (the FQBN suffix `opt=o1std`) compiles cleanly and the
build still fits comfortably. If you build from the Arduino IDE instead, pick
**Tools → Optimize → "Fast"** (= -O1).

## Footprint (Teensy 4.1, -O1, teensy:avr 1.62.0)

```
FLASH:  code 316 KB, data 33 KB        free for files 7.7 MB
RAM1:   variables 224 KB, code 252 KB  free for local vars ~37 KB
RAM2:   variables 65 KB                free for malloc 459 KB
EXTRAM: 16.5 MB
```

> **Hardware requirement:** TŒRN uses ~16.5 MB of PSRAM, so the Teensy 4.1 must have
> **both PSRAM chips soldered** (16 MB). Without them the firmware will not run.

## OLED HUD

The `IchosOled` library is a self-contained, minimal SSD1306 text driver — **not**
Adafruit_GFX or U8g2. Those push several KB of code into RAM1 (Teensy 4 runs code from
ITCM by default) and TŒRN leaves only ~700 bytes of RAM1 free, so they overflow the
link. Every function in `IchosOled.cpp` is marked `FLASHMEM` (stays in flash) and the
5×7 font is `PROGMEM`, so the HUD costs ~80 bytes of RAM1. It shares the Wire bus with
the audio codec (SDA=18, SCL=19) and shows:

```
CH:5            >PLAY
MODE: DRAW
BPM:  120
VOL:80  PAGE:1
```

`build_toern.py` wires it in automatically (lightweight include + `ichosOledBegin()` at
the end of `setup()` + a one-line `ichosOledRender(...)` glue in `loop()` reading TŒRN's
globals). The bus runs at 400 kHz (both chips support it) and each `ichosOledRender()`
call rewrites at most **one** changed, space-padded text row (~3 ms) — no full-screen clears
— so it never stalls the sequencer, button polling or MIDI input.

## Feature trims

`build_toern.py` applies the requested lightening as build-time patches (the vendored
TŒRN sources stay pristine). Currently trimmed: the optional reactive **2nd LED strip**
(256 LEDs) — its `addLeds` on pin 24 and per-frame update are removed, freeing pin 24
and a little CPU. See `_DOCS/FEATURE_INVENTORY.md` for the full feature catalogue and
the `REMOVE_*` flags at the top of `build_toern.py`.

## Remaining work

- **On-hardware verification** — flash and confirm encoder direction, button polarity,
  and combos behave as mapped in `_DOCS/MAPPA_CONTROLLI.md`; check the SD on the built-in
  slot and LINE IN recording. If one encoder click moves two steps, set
  `ICHOS_ENC_COUNTS_PER_DETENT` to 2.
- Upstream TŒRN opens `ERROR.txt` (crash report) with a mode the Teensy SD library
  doesn't accept, so that log is never written — harmless, left as is.

The desktop emulator (`emulator/`, target `toernemu`) already runs all 23k lines of
TŒRN with host shims that mirror these same drivers — use it to rehearse the control
mapping before touching hardware.
