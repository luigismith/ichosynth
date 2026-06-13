# TŒRN emulator port — status & roadmap

Goal (user, 2026-06-12): run the **real TŒRN firmware** in the emulator (same
shim technique as the NI404 build) to get ALL its features, **plus render the
user's SSD1306 OLED HUD** (`../soundpauli_ni404.ino`'s display.h) as a window panel.

Source cloned to `emulator/toern-src/` (https://github.com/soundpauli/toern,
MIT). **23,442 lines** across 12 .ino files (~8× NI404). `toern.ino` is 328 KB.

## TŒRN feature set (what running the firmware gives us)
16 channels: 8 sample voices, 1 three-voice poly synth (ch11, 10 presets), 2 mono
synths (ch13/14, LFO + arpeggiator). Per-channel effects: ADSR, **bitcrusher**,
filters (LP/HP/BP + **Moog ladder**), **reverb (freeverb)**. Probability +
conditional triggers, velocity, mute/solo, pattern modes (OFF/ON/SONG/NEXT), song
mode (64 patterns), 999 patterns/samples, 100 samplepacks. Sample trim/reverse,
**live recording** (mic/line-in), 4 RGB-I2C encoders, 3 touch switches, TRS MIDI.

## New dependencies vs the NI404 build
### Audio nodes (from toern-src/audioinit.h — 192 connections!)
- [x] AudioAmplifier, AudioEffectBitcrusher, AudioSynthWaveformDc,
      AudioAnalyzePeak, AudioFilterLadder  → `compat/audio_extra.h` (compiles; NI404 regression OK)
- [x] I/O stubs: AudioInputI2S (silence), AudioRecordQueue (no data),
      AudioPlaySdWav (silent/not-playing), AudioEffectGranular (passthrough)
- [x] AudioEffectFreeverbDMAMEM — **vendored** `toern-src/src/effect_freeverb_dmabuf.cpp`
      compiles against our AudioStream when built with `-D__ARM_ARCH_7EM__` (its
      update() body is portable C, gated on that macro). **Verified: reverb tail
      present after input stops (0.19).** Needs per-file define in CMake.
      Required: audio_block_t aligned to Teensy's 3-field layout (done in Audio.h);
      shims `compat/AudioStream.h`, `compat/utility/dspinst.h`, `__disable_irq/_enable_irq`.
- [ ] (reuse) AudioMixer4, AudioEffectEnvelope, AudioSynthWaveform,
      AudioFilterStateVariable, AudioPlayArrayResmp, AudioOutputI2S, SGTL5000
- [ ] AudioDesign (1 use) — investigate (likely a custom/typo)

### Peripheral libraries  — ALL DONE (compile + run together)
- [x] `i2cEncoderLibV2.h` — 4 RGB I2C encoders → host encoder/button slots (by
      construction order); clamped counter + callbacks (onButtonPush/Release/
      Increment/Decrement/Change/Max/Min); RGB stored for future on-screen colour.
- [x] `MIDI.h` (+ `Serial1..8` globals) — TRS MIDI over Serial8, shares usbMIDI's
      real-input queue via `usbMIDI.poll()`; read()/getType/getData1/2/getChannel,
      setHandle*, MIDI_CREATE_*_INSTANCE macros, `midi::` enum, DefaultSettings.
- [x] `FastTouch.h` — `fastTouchRead(pin)` for SWITCH_1/2/3 → host touch slots 5/6/7.

### Display (user's OLED)
- [ ] Render the SSD1306 HUD. Provide Adafruit_GFX/Adafruit_SSD1306 shims writing
      to a 128×64 mono framebuffer; draw it as a panel beside the LED grid in
      main.cpp. (toern itself is LED-matrix-only; the OLED HUD is from the NI404
      fork's display.h — bring it into the toern build with OLED_ENABLED=1.)

## Firmware integration plan
- [ ] `src/firmware_toern.cpp`: `#include` toern.ino + the toern_*.ino files
      (Arduino concatenates all .ino in a sketch folder — replicate by including
      each, or a single TU that includes them in order). Generate Arduino-style
      prototypes (as for NI404: `ni404_prototypes`-style) across ALL toern_*.ino.
- [ ] config: toern uses 4 encoders + I2C; provide its pin/HW config.
- [ ] CMake: a second target `toernemu` (or a `-DFIRMWARE=toern` switch) selecting
      firmware_toern.cpp + toern-src include dir; same audio_engine/host_io/midi.
- [ ] Compile-iterate the 23k lines against the shims (expect many rounds:
      missing APIs, OOB/UB fixes like the NI404 `lastFile` one, -fpermissive).
- [ ] Verify headless (--verify style) + interactive.

## Effort estimate
Multi-session. NI404 (2845 lines) took a full build-out; toern is ~8× plus more
shims + display + recording. Realistic order: freeverb → peripheral shims →
firmware glue+prototypes → compile-iterate → display → recording/granular polish.

## Done so far
- Researched toern; confirmed approach (run real firmware) with the user.
- Cloned source; inventoried all new audio nodes + libraries.
- New audio-node shims (`compat/audio_extra.h`) — compile, NI404 regression OK.
- **Freeverb** vendored compile path solved + verified (reverb tail).
- **All 3 peripheral shims** (i2cEncoderLibV2, MIDI.h, FastTouch) compile + run together.
- audio_block_t aligned to Teensy layout (no NI404 regression — still 8/8 channels).

## FIRMWARE GLUE + COMPILE — DONE ✅
- `src/firmware_toern.cpp` includes toern.ino + all 11 toern_*.ino in Arduino
  concatenation order; `src/toern_prototypes.h` AUTO-GENERATED (408 fns; keeps
  static/FLASHMEM; strips default args; handles `) { // comment`; forward-decls
  structs + typed enums; includes icons.h for `enum IconType`; defines
  NUM_ENCODERS / SAMPLE_BROWSER_NAME_MAX; fwd `enum class DrawRFullMuteUnmuteMode`).
- CMake `toernemu` target builds firmware_toern + audio_engine/host_io/midi_* +
  the vendored freeverb (with `-D__ARM_ARCH_7EM__` on that file only). `-fpermissive`.
- **THE FULL 23,442-LINE TŒRN FIRMWARE COMPILES, LINKS, BOOTS and RUNS** — `--selftest`
  OK: setup()+loop() execute, no crash, MIDI dispatch works (encoder/button driven).
  Needed extra shim bits this round: pgmspace.h; elapsedMillis via Arduino.h; A0–A23;
  HardwareSerial peek/readBytes; Serial1..8; CHSV + hsv2rgb_rainbow/rgb2hsv_approximate
  + blend + nscale8_video + CRGB+=; File:public Print + isDirectory/openNextFile/name
  + O_* flags; SGTL5000 micGain/lineInLevel/eq*/enhanceBass*/surround*/etc.;
  AudioSynthWaveform.pulseWidth; NVIC_SET_PRIORITY/IRQ_*/dtostrf; IntervalTimer.priority;
  SD rmdir/rename; i2cEncoder constants moved to scoped static members; `sbrk` stub.
- NI404 regression: still builds + 8/8 channels sound.

## WINDOW VERIFICATION + OLED PANEL — DONE ✅
- **LED render bug fixed**: toern calls FastLED.addLeds TWICE (main matrix `leds`
  then external `stripLeds`); the shim kept the LAST -> published the black strip.
  Now the FIRST addLeds (the matrix) wins. toern LEDs light (62 lit frames),
  NI404 still 61.
- **Print routing bug fixed**: Print::print() now routes through the virtual
  write() (was hardcoded to stdout), so Adafruit_GFX/File subclasses work. Verified
  "NI404" renders into the OLED framebuffer.
- **OLED panel implemented + verified**: compat/Wire.h, Adafruit_GFX.h (built-in
  5x7 font), Adafruit_SSD1306.h (128x64 mono framebuffer) -> host_io bridge
  (ni404_publish_oled / ni404_get_oled) -> main.cpp draws it below the LED grid.
  - NI404: display.h HUD with OLED_ENABLED=1 -> 975 lit px (mode/BPM/Vol/Page).
  - toern: self-contained HUD in firmware_toern.cpp (currentMode->name / SMP.bpm /
    lastPage) -> 757 lit px.
- selftest now advances real time (3ms/iter) so millis()-gated redraws fire.

## DONE
- Window launches (static-linked mingw runtime + DLLs shipped beside the exe).
- **4th encoder + touch wired**: keyboard map = Q/A W/S E/D R/F (4 encoders turn),
  Z X C V (encoder buttons), B (NI404 filter), 1 2 3 (toern touch SWITCH_1/2/3).
  Host slots BTN_TOUCH1/2/3 = 5/6/7. Key legend printed at startup.
- **16x16 view** kept (user chose 16x16 over 32x16; renderer shows the matrix).
- **Sample kit on SD**: `scripts/gen_samples.cpp` -> 12 one-shots (kick/snare/hats/
  clap/rim/tom/cowbell/bass/blip/stab/sweep) as 16-bit mono 44.1k WAV in
  `../_SDCARD/3/` (_300.._311) + README. Verified: load+play through the resampling
  voice (peaks 0.77-0.88). Non-destructive (packs 0/1/2 untouched).

## CODE-REVIEW (high) + HARDENING — DONE
Ran /code-review high (3 finder angles x ~6 candidates, verified). Fixed:
- main.cpp: SDL_CreateRenderer NULL-checked + software fallback (no startup crash).
- audio_extra.h Bitcrusher: int32 sign-extended mask (negative samples no longer mangled).
- audio_engine.cpp SVF: cutoff capped ~Fs/5 + NaN/runaway backstop (filter can't latch dead).
- audio_engine.cpp Envelope: mult clamped [0,1] in BOTH branches (no polarity flip/clicks).
- audio_extra.h FilterLadder: rewrote as linear 4-pole (real 24 dB/oct) + stability clamp;
  verified it attenuates a 4 kHz tone at 150 Hz cutoff (0.54 -> 0.22) and stays stable.
- gen_samples.cpp 310/311: persistent 1-pole filters (swept LP works, not raw noise).
- midi_in.cpp CoreMIDI: correct per-status message length + SysEx skip (Mac).
- i2cEncoderLibV2.h: onMax/onMin fire only on the transition reaching the limit.
Verified headless: NI404 8/8 audio, both LED+OLED render; effects (bitcrush/ladder/freeverb) process audio.

ACCEPTED (not bugs for these firmwares / benign):
- Param-setter "race" (amplitude/frequency/gain written main-thread, read audio-thread):
  single-float stores are atomic on x86 and no setter writes coupled multi-fields, so it's
  benign — matches the device's own lock-free param updates. Left as-is.
- SD FILE_WRITE truncates (vs Teensy append): both firmwares write WHOLE files sequentially
  (no seek+partial-write on a write handle), and loads read by markers/fixed size, so
  truncate is correct/cleaner here. Verified by grep.

## SETTINGS MENU (in-window, TAB) — DONE
src/menu.{h,cpp}: overlay toggled by TAB. Audio OUTPUT device select (enumerates
SDL devices, reopens on change), MASTER VOLUME (output makeup gain 0..64x in the
audio engine: ni404_set_master_gain), AUDIO INPUT device list, MIDI input device
list + mapping info, key legend. Persists to settings.txt. The menu now OWNS the
SDL audio device (menu_init/menu_shutdown). Text drawn with the 5x7 font.

## MPK Mini IV (mk4) MIDI — DONE (interactive learn)
Found via a winmm listener (tools/midi_listen.cpp): knobs are RELATIVE encoders on
CC 24/25/26/27 (port MIDIIN2), pads = notes 36-43. Fixes: midi_in opens ALL ports
(knobs are on a 2nd port), midi_map handles relative mode (knobmode=relative) + the
mk4 defaults, note de-dup for multi-port mirroring. All in midi-map.txt (editable).

## FIXED (2026-06-13) — audio level ~100x too quiet was a STALE autosaved.txt
Root cause found with per-stage output taps (--stagetest, since removed):
- voice 0.999, env 0.829, FILTER 0.038 (21x drop!), mixer_end 0.019 -> output 0.002.
- The filter1 live cutoff read back as **fc=20 Hz** (the min clamp), not 9 kHz.
  setup() opens all filters (applyAllFilters, 9 kHz) then autoLoad() reads the whole
  SMP struct from _SDCARD/autosaved.txt and RE-applies filters from the loaded
  filter_knob[]. That stale dev-created autosave had filter_knob[]=0 (invalid: the
  live range is 1..maxfilterResolution), so mapf(0,...) underflowed below
  FILTER_MIN_HZ and the cutoff clamped to 20 Hz -> ~20x loss. The same file also had
  SMP.vol=1 -> sgtl5000 master 0.1 -> a further 10x. ~200x combined = the 0.002 bug.
  The SVF itself was never the culprit (passband gain ~1.0 below cutoff, verified).
- FIX (firmware, [emu], hardware-safe): loadPattern() now sanitizes filter_knob[]
  after the struct read — any value <1 or >maxfilterResolution defaults to fully
  open. Protects real hardware from pre-filter-era / corrupt saves too.
- The stale autosaved.txt was cleared (renamed *.bak2); boot now uses defaults.
- VERIFIED: --verify channels 0.36-0.45 (8/8), --demotest peak 0.52, selftest OK.
  SVF kept at 4x oversampling (harmless stability win, not the fix).

## FIXED (2026-06-13) — LED grid was rendered vertically flipped
On-grid text/digits showed upside down. The firmware's logical y increases UPWARD
(showNumber draws glyph-top at the highest y via `ypos = maxY - topY`, then `ypos -
number[..][1]`; logo/noSD use the same `maxY - y`), so y=1 is the BOTTOM physical
row. main.cpp drew y=1 at the top. FIX: render screen row = (GRID-1) - (y-1) — a
pure vertical flip; column de-serpentine unchanged (x already correct). Applies to
both targets (shared main.cpp; NI404 is a toern fork, same panel wiring).

## NEXT (lower priority / needs the GUI or hardware)
- Recording (mic/line-in via SDL audio capture) + granular (still stubs).
- Optional 32x16 view; quiet toern Serial debug spam (firmware prints to stdout).
