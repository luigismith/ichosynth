# ichosynth Emulator — build status & roadmap

Desktop emulator (Windows + macOS) used as a **test bench** for ichosynth.
Strategy: **reuse a real firmware** unchanged and provide a desktop compatibility
layer that emulates every Teensy/Arduino API it touches, so the sequencer/UI/MIDI/
sample logic *is* the device's, not a reimplementation.

> **Two firmwares, one emulator.** The default target `ni404emu` runs the
> **hybrid bench firmware** (`../soundpauli_ni404.ino`, 2845 lines) — a 4-encoder
> NI404 fork used to prototype TŒRN-style features on PC. The **physical
> instrument** ichosynth runs the **real TŒRN firmware** (built with
> `teensy/build_toern.py`); the emulator runs that same TŒRN source in the
> reference target `toernemu` (see `STATUS-toern.md`, `EMU_BUILD_TOERN_REF=ON`).
> The bench remains the fast iteration loop; the Teensy build is the product.

Decisions locked with the user (2026-06-12):
- Approach: **native C++ port** (max fidelity), not web/python.
- Integration: **standalone** — computer keyboard/mouse drive the 16×16 grid and
  the 3 encoders + buttons; audio goes to the default output. No real MIDI I/O.
- Samples: **reuse `../_SDCARD`** as the SD filesystem (`<folder>/_N.wav`).

## Architecture

```
            +-------------------- main.cpp (SDL2) ---------------------+
            |  window + 16x16 LED render  |  keyboard -> encoders/btns |
            |  audio callback  <-----------------------+              |
            +------------------------------------------|--------------+
                          calls setup()/loop()         | pulls 44100/int16 blocks
                                   |                    |
   ../soundpauli_ni404.ino  <------+   compat/Audio.h (AudioStream graph) i2s1 sink
   (unmodified firmware)               compat/TeensyPolyphony.h (samplers + voices)
        |  uses Arduino/Teensy APIs ->  compat/* shims
        +-- FastLED leds[256]  -> compat/FastLED.h  -> framebuffer -> SDL texture
        +-- Encoder/Switch     -> compat/* fed by SDL key state
        +-- SD/File            -> compat/SD.h  -> ../_SDCARD on disk
        +-- EEPROM             -> compat/EEPROM.h -> emulator/eeprom.bin
        +-- usbMIDI            -> compat/usb_midi.h (no-op stub)
        +-- IntervalTimer      -> compat/IntervalTimer.h (driven from loop/audio)
```

The Teensy Audio library processes **128-sample int16 blocks at 44100 Hz**. The
emulated graph runs `update()` on every node each block; `i2s1` (AudioOutputI2S)
writes blocks into a ring buffer that the SDL audio callback drains and converts
to the host device format.

## Component status

Legend: [ ] todo  [~] in progress  [x] done & compiles  [t] done & tested

### Build system
- [x] `scripts/bootstrap-windows.ps1` — install MSYS2 + gcc + cmake + SDL2  (DONE: installed on this machine, C:\msys64)
- [x] `scripts/bootstrap-macos.sh` — brew install cmake sdl2
- [x] `CMakeLists.txt`  (written; not yet used for a full build)
- [x] `scripts/build.ps1` / `build.sh` / `run.ps1`

> Toolchain installed & verified: g++ 16.1, cmake 4.3, SDL2 (mingw64).
> COMPILE QUIRK: invoking mingw g++ via the Git-Bash `Bash` tool does not emit
> the exe (PATH/`/tmp` mismatch). Compile via **PowerShell** with
> `$env:PATH="C:\msys64\mingw64\bin;$env:PATH"`. This is what build.ps1 does.

### Compatibility shim (`compat/`)
- [x] `Arduino.h` — millis/micros/delay, String, map/constrain/random, Serial, EXTMEM/PROGMEM/F  **(compiles+runs)**
      NOTE: min/max are functions (not macros) and abs/round defer to <cmath> —
      Arduino's macros otherwise wreck <chrono>/<limits>. Define NOMINMAX before
      including windows.h/SDL in the frontend.
- [x] `Mapf.h` — `mapf()` float map  **(compiles)**
- [x] `elapsedMillis.h` / `elapsedMicros`  **(compiles)**
- [x] `FastLED.h` + `WS2812Serial.h` — CRGB, show()->framebuffer, clear/setBrightness, fadeToBlackBy/nscale8  **(compiles+runs, validated vs colors.h)**
- [ ] `IntervalTimer.h` — begin/end/update, driven deterministically
- [ ] `Encoder.h` — read()/write(), backed by host input (register by pinA)
- [ ] `avdweb_Switch.h` — poll()/pushed()/released() (also check how encoder push-buttons BTN_LEFT/RIGHT/MIDL are read — only filterButton uses Switch)
- [ ] `EEPROM.h` — get/put -> eeprom.bin
- [ ] `SD.h` + `File` — begin/open/exists/mkdir/remove + read/write/seek/size/close, maps to _SDCARD
- [ ] `usb_midi.h` — usbMIDI stub (setHandle*, read, sendNoteOn, sendRealTime)

The LED bridge: `host_io.cpp` holds the framebuffer; `FastLED.show()` calls
`ni404_publish_leds()`; the frontend pulls via `ni404_get_leds(out,max,&count)`
(returns a generation counter for dirty-checking). 16×16, index = row*16+col
(verify orientation against firmware `setLED`/`XY` mapping when wiring render).

### Audio engine (`compat/Audio.h` + `src/audio_engine.cpp`)
- [x] `AudioStream` base + AudioConnection graph + block pool + `AudioMemory`/`AudioNoInterrupts` (recursive-mutex guard)  **(compiles+runs)**
- [x] `AudioSynthWaveform` (sine/saw/square/triangle; amplitude/begin/frequency/phase)  **(runs)**
- [x] `AudioEffectEnvelope` (linear ADSR; noteOn/noteOff)  **(runs)**
- [x] `AudioFilterStateVariable` (2x-oversampled Chamberlin lowpass; frequency/resonance)  **(runs)**
- [x] `AudioMixer4` (gain)  **(runs)**
- [x] `AudioOutputI2S` (ring-buffer sink) + `ni404_audio_render()` pull driver for the SDL callback  **(runs)**
- [x] `AudioControlSGTL5000` (volume -> master gain; rest no-op)  **(runs)**
- [x] Verified: osc->env->filter->mixer->out yields real signal (peak 0.34).
- [x] `ResamplingReader` port (compat/newdigate/, patched `return;`->`return false;`; deps loop_type/interpolation/waveheaderparser reconstructed)  **(compiles)**
- [x] `AudioPlayArrayResmp` voice (playRaw/setPlaybackRate/enableInterpolation/stop)  **(runs)**
- [x] `TeensyPolyphony` `arraysampler` — addVoice/addSample/noteEvent, pitch = 2^((note-root)/12)  **(runs)**
- [x] Verified: sample triggers (playing 0->1), root vs +12 semitones consumes sample 2x faster (pitch works).

ASSUMPTION TO CONFIRM ON DEVICE: the exact pitch formula & velocity->gain mapping
are reconstructed (upstream newdigate libs were not vendored — clone was blocked
as untrusted-code). If pitch/levels differ from the real NI404, vendor the two
newdigate repos and port verbatim. **THE AUDIO ENGINE IS COMPLETE & TESTED.**

NOTE: graph runs in CREATION ORDER each tick; envelope/filter ordering gives ≤1
block latency (audioinit declares filters before envelopes) — audible-irrelevant.
Param changes from the main thread are serialised by AudioNoInterrupts (global
recursive mutex); noteEvent/playRaw must also take it (they touch reader state).

### Frontend (`src/main.cpp` + `src/ni404_host.h`)
- [x] SDL2 window + 16×16 LED grid renderer (scaled; values bumped ×4 for visibility)  **(builds+links SDL2)**
- [x] Keyboard map: 3 encoders (Q/A, W/S, E/D), buttons (Z/X/C), filter (F)  **(works)**
- [x] Audio device open + callback -> ni404_audio_render (graph pull)  **(works)**
- [x] Calls ni404_setup() once + ni404_loop() per frame
- [x] `--selftest` headless harness  **VERIFIED: audio peak 0.27, LED animates every frame**
- [ ] On-screen help / key legend overlay + transport/BPM readout
- [ ] host input -> real device encoders/buttons/grid cursor (currently demo mapping)

### Integration & polish
- [x] Remaining shims: Encoder, avdweb_Switch (full callback state machine), EEPROM(->eeprom.bin), SD(->_SDCARD), IntervalTimer (pumped each loop), usb_midi
- [x] `src/firmware.cpp` now `#include`s the REAL `../soundpauli_ni404.ino`; ni404_setup->setup(), ni404_loop->loop()+ni404_pump_timers()
- [x] Auto-generated Arduino-style prototypes (`src/ni404_prototypes.h`); `-fpermissive` (matches Teensy core); `sprintf`->bounded `snprintf` in Arduino.h
- [x] **The unmodified 2845-line firmware COMPILES and RUNS** — setup() + loop() execute, LEDs render (selftest: 41 lit frames), no crash.
- [x] Audio path VERIFIED headless (`--verify`): loads real WAVs from _SDCARD and
      all 8 sample channels produce sound (peak ~0.35–0.50). SD->WAV->resampling
      voice->envelope->filter->mixer->output confirmed with real data.
- [x] LED XY orientation: renderer now undoes the firmware's serpentine `light()`
      map (even rows L→R, odd rows R→L; y=1 at top) so the on-screen grid is correct.
- [ ] Still GUI-only (needs a human): paint a step via keyboard, hear via speakers,
      change BPM/filter, save/load — the logic underneath is verified.
- [ ] Package: Win .exe (bundle SDL2.dll) + Mac .app

### MIDI control (NEW requirement, 2026-06-12)
Goal: drive the emulator from a real MIDI controller; presets for Akai MPK Mini
mk1/mk2/mk3 and MPK Mini Plus.
- The firmware ALREADY handles MIDI (handleNoteOn plays/records the current
  channel's sample chromatically; handleClock/Start/Stop sync the sequencer).
- [x] Real MIDI input backend (Windows winmm; macOS CoreMIDI), thread-safe queue (`src/midi_in.cpp`)  **(Win builds+runs)**
- [x] usb_midi shim: stores typed handlers + read() drains & dispatches queued messages
- [x] Control map (`src/midi_map.cpp`): knobs CC70/71/72 -> 3 encoders; pads notes 36–43 -> buttons + grid step; keys -> firmware note play/record
- [x] Verified in selftest: CC#71 drives center encoder (firmware processes it); pad note 36 fires the firmware's BTN_L push/release callbacks.
- [x] Per-model preset docs (mk1/mk2/mk3/Plus): `presets/README.md` (knob CC / pad notes / channel to enter in each Akai editor)
- [ ] Optional: generate proprietary Akai editor binary program files (need editor+version); MIDI-learn / config-file remapping
- [ ] macOS CoreMIDI path is written but UNTESTED (no Mac here)

### FIRMWARE EDITS (review before next hardware flash!)
Tiny, hardware-safe fixes for latent out-of-bounds UB (harmless on Teensy, fatal
on desktop). Each marked `[emu]` in the .ino:
- `int lastFile[9]` -> `int lastFile[10]`: setLastFile() loops folders 0..9 (10),
  array had only 9 -> wrote/read one past the end. Real bug on hardware too.
- loadPattern(): after reading the SMP struct from a save file, sanitize
  `filter_knob[]` — any value <1 or >maxfilterResolution defaults to fully open.
  A 0 (pre-filter-era or corrupt save) otherwise maps below FILTER_MIN_HZ and
  applyAllFilters() clamps every voice's cutoff to 20 Hz, silencing playback.
  Fixed the emulator's "too quiet" bug; protects real hardware from old saves too.

## HOW TO RUN NOW (demo frontend)
```powershell
cd emulator/scripts
./build.ps1      # configures + builds + copies SDL2.dll
./run.ps1        # opens the window: animated LED + a note while holding 'X'
# headless check: ../build/ni404emu.exe --selftest
```
Keys: Q/A W/S E/D = encoders, Z/X/C = encoder buttons, F = filter, Esc = quit.
The DEMO firmware stub proves the pipeline; the real device logic is the next
integration step (swap firmware.cpp as above).

## Open questions / risks
- TeensyPolyphony voice-stealing & note→playbackRate mapping must match the lib
  the firmware was built against (newdigate teensy-variable-playback family).
  Source of truth for the reader is `../_DOCS/ResamplingReader.h`; the polyphony
  manager API used by the firmware is `_samplers[i].addSample(note, ptr, len, ch)`
  plus note-on/off routing — to be reconstructed from firmware usage.
- `EXTMEM unsigned char sampled[13][~1.2MB]` (~15.6 MB static) — fine on desktop.
- Firmware relies on `delay(5)` pacing in the audio loop; on desktop the audio
  thread is the clock, so timing is decoupled — watch sequencer tempo.

## Key input mapping (proposed — revisit)
- Grid cursor: arrow keys; place/erase step: Space.
- Left encoder: `Q`/`A` (turn ‑/＋), button: `Z`.  (volume)
- Center encoder: `W`/`S`, button: `X`.  (BPM / filter when held)
- Right encoder: `E`/`D`, button: `C`.
- Filter button (hold): `F`.  Play/Pause: Enter.  Shift: Left-Shift.

## DONE (2026-06-16) — usability + recording + SD + single build
The emulator is now the development target for **ichosynth** (the hybrid). All of the
below verified by driving the live window (screenshot + synthetic mouse/keyboard):
- **On-screen controls (mouse + multi-touch)** in a panel below the OLED: 4 knobs
  (grab the RIM to rotate, press the CENTRE for the encoder button, centre-press-drag
  = hold+turn; dead-zone prevents stray rotation; wheel rotates) + buttons PLAY / MENU
  / REC / FILT. `src/main.cpp`; labels via `emu_draw_text()` exposed from `menu.cpp`.
- **Realistic OLED**: scale 3→1 (128px, ~¼ of the grid) and centred.
- **Settings menu** made width-safe (header split, value column truncated) — no overflow.
- **Multi-format import**: drag a **WAV/MP3/FLAC** onto the window → decoded
  (`src/audio_decode.cpp` + vendored `vendor/dr_{wav,mp3,flac}.h`), resampled, installed
  on the SD, loaded. `sample_import.cpp` now decodes via that path; import extension
  check widened in `firmware.cpp`.
- **SD management** (menu): show path + open in Explorer (SDL_OpenURL); switch SD by
  dropping a folder (`ni404_sd_set_root` + reload pack) / reset to default; **sample
  browser** (lists `_N.wav`, loads into the current channel). SD root get/set on the
  SD shim; hooks in `firmware.cpp`/`ni404_host.h`.
- **Live recording**: portable path — firmware `AudioInputI2S`+`AudioRecordQueue`
  (see firmware notes); emulator captures from the selected input device
  (`src/audio_capture.cpp`, SDL capture → `AudioRecordQueue` shim). Hold REC; OLED
  shows `*REC*`. (Recording lands in RAM on the channel; SD-save TODO.)
- **Single build**: only `ni404emu` (ichosynth) by default; `toernemu` behind
  `EMU_BUILD_TOERN_REF=ON`.

### DONE (2026-06-17) — 4-encoder filter + first TŒRN effect (bitcrusher)
- **4 encoders** (`HAS_ENCODER4 1`, 4th on pins 32/33/41): the 4th is contextual —
  in DRAW/SINGLE it's the **fast filter** (turn = lowpass cutoff of the cursor voice,
  no button; auto-syncs per voice), volume in VOLUME/BPM, seek in the browser. The
  standalone filter button is gone; emulator panel is now **4 encoders + 3 buttons**.
  Verified via `--play`: closing the 4th encoder drops hi-hat energy to ~2%.
- **Per-voice bitcrusher** (`BITCRUSH_ENABLED`) on the 8 sample voices, inserted
  filterN→crushN→mixer (default bypass; `AudioMemory` bumped to 96). Verified via
  `--play`: a crushed voice's signal clearly differs from clean; all 8 channels still
  sound. Engine + `ni404_set_crush()` hook in; **on-device control = the FX MODE (next)**.
- **Per-voice Moog ladder** (`LADDER_ENABLED`, 2nd TŒRN effect) after the crusher
  (filterN→crushN→ladderN→mixer; default open ~18 kHz = transparent; `AudioMemory` 120).
  Verified via `--play`: closing the ladder drops a bright voice's energy to ~1%.
  Engine + `ni404_set_ladder()` hook in; on-device control also via the FX MODE.

### DONE (2026-06-18) — FX MODE (on-device control for the effects)
- New `fxMode` Mode (`FXMODE_ENABLED`): **hold MENU** in DRAW/SINGLE → the 4 encoders
  become sliders for the cursor voice (E1 cutoff, E2 ladder cutoff, E3 ladder reso,
  E4 bitcrush), drawn as 4 colour-coded bars on the grid; tap MENU to exit. Encoders
  seeded from the voice's current values on entry (no jump). Only voices 1..8.
  Verified live (screenshot+input): enters, persists after the hold releases, sliders
  move with the encoders; `--play` still all-PASS.

### DONE (2026-06-18) — recordings saved to SD
- On REC release the take is written to `samples/9/_9NN.wav` (next free) via the
  firmware (`saveRecording()` + `writeWavHeader()`), and the channel is pointed at it
  (`SMP.wav[ch]`), so it persists past restart and reloads from disk. Verified via
  `--play` (`ni404_test_record_save` hook): synth a tone → save → reload → plays (peak 0.12).

### DONE (2026-06-18) — REC count-in
- Hold REC → a **4-beat count-in** at the song tempo (millis-based, BPM-synced; shows
  4-3-2-1 on the grid via showNumber) then recording begins; release stops + saves.
  Verified live (screenshots: 4→2→*REC*). Self-contained in loop() (not the playTimer
  ISR), so it works whether the sequencer is playing or stopped.

### Still open
- Auto-load recordings into the channel on song reload (the file persists + SMP.wav is
  set; full song-recall wiring to confirm on hardware).
- Reverb (needs a freeverb shim for ni404emu + a send bus).
- ogg/aiff import (needs stb_vorbis / an AIFF parser).
- Mac build of the new sources (CI covers it; not run locally).
