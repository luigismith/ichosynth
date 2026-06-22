[🇮🇹 Italiano](MANUALE_USO.md) · **🇬🇧 English**

<div align="center">

# 🎮 ichosynth — Usage Manual

### How to play the sampler-sequencer you *draw*

You draw music on a 16×16 grid with **4 knobs** and **3 buttons**. No computer, no menus to memorize: turn, press, listen.

[![Level: Beginner](https://img.shields.io/badge/Level-Beginner-2ea44f.svg)](#)
[![Build: 4 encoders + 3 buttons](https://img.shields.io/badge/Build-4%20encoders%20%2B%203%20buttons-orange.svg)](#)
[![Firmware: TŒRN by SP_](https://img.shields.io/badge/firmware-T%C5%92RN%20%C2%B7%20SP__-blueviolet.svg)](https://toern.live)
[![See also: Build](https://img.shields.io/badge/See%20also-Build%20Manual-blue.svg)](BUILD_MANUAL.md)

</div>

> 🎧 **You don't need a computer to play**: your **ichosynth** generates everything on its own. Plug in
> your **headphones**, power it via USB, and off you go.

> 🔌 **Connections — getting sound out (and in)**: the instrument has three audio jacks.
> - **Line Out** — 2× **6.35 mm (1/4") MONO** jacks, **L + R = stereo**. Plug them into an amplifier,
>   mixer, PA or audio interface. The output is stereo (TŒRN pans the voices), so use **both L and R**;
>   for a mono rig just use the **L** jack.
> - **Line In** — 1× **6.35 mm (1/4") MONO** jack. Feed in an instrument, another synth, a field
>   recorder or a mixer send to **record/sample it** (see [ch. 16](#16--live-recording-rec)).
> - **Headphone** — the on-board **3.5 mm stereo** jack, for monitoring.
>
> All three jacks share the device's ground, and **Line Out and headphone play at the same time** — no
> menu setup needed.

> ℹ️ **This is the real TŒRN.** ichosynth runs the full **TŒRN firmware** (by SP_/soundpauli,
> [toern.live](https://toern.live)) on a Teensy 4.1, built with cheap hand-soldered parts: **4 KY-040
> encoders**, **3 tact switches** and an **SSD1306 OLED**. Where the original TŒRN told you the state
> with the glowing colour of its encoder rings, our build shows it as plain text on the **OLED**.

---

## 📑 Table of Contents

- [1 · The concept in 30 seconds](#1--the-concept-in-30-seconds)
- [2 · The hardware: 4 knobs + 3 buttons](#2--the-hardware-4-knobs--3-buttons)
- [3 · Reading the grid and the OLED](#3--reading-the-grid-and-the-oled)
- [4 · The 3 buttons (B1 B2 B3)](#4--the-3-buttons-b1-b2-b3)
- [5 · DRAW mode (drawing)](#5--draw-mode-drawing)
- [6 · Pages, patterns and subpatterns](#6--pages-patterns-and-subpatterns)
- [7 · Mute (silencing voices)](#7--mute-silencing-voices)
- [8 · Volume and BPM](#8--volume-and-bpm)
- [9 · Velocity, probability and conditions](#9--velocity-probability-and-conditions)
- [10 · SINGLE mode (one voice only)](#10--single-mode-one-voice-only)
- [11 · FILTER mode and per-voice DSP](#11--filter-mode-and-per-voice-dsp)
- [12 · Changing the sample (Sample Browser)](#12--changing-the-sample-sample-browser)
- [13 · Voice colors and the synth voices](#13--voice-colors-and-the-synth-voices)
- [14 · Sample packs](#14--sample-packs)
- [15 · Saving and loading (Menu)](#15--saving-and-loading-menu)
- [16 · Live recording (REC)](#16--live-recording-rec)
- [17 · SONG mode](#17--song-mode)
- [18 · MIDI and tap-tempo](#18--midi-and-tap-tempo)
- [19 · Mode & command map](#19--mode--command-map)
- [20 · Common problems](#20--common-problems)

---

## 1 · The concept in 30 seconds

The **16×16 grid** is your music sheet. A playback "playhead" runs from left to right: every column it
touches plays the notes you've put there.

<p align="center">
  <img src="assets/grid-concept.svg" alt="The 16x16 grid: rows = colored voices, columns = steps, Play playhead" width="560">
</p>

- The **columns** (left→right) are the **16 steps** of one bar (a page can be chained to **32×16**).
- Each **row** is a **voice** (a sample or a synth), identified by a **color**.
- Several pages in a row make up a **pattern**; several patterns make up a **song**.

> 💡 Basic flow: **draw notes → press PLAY (B1) → loop**. You change samples, BPM and volume on the fly, without stopping.

---

## 2 · The hardware: 4 knobs + 3 buttons

On top there are **4 encoders** — **E1 E2 E3 E4**, left to right. Below them sit **3 tact switches** —
**B1 B2 B3**. Every encoder both **turns** and **pushes** (click).

```
   [ E1 ]   [ E2 ]   [ E3 ]   [ E4 ]     ← 4 knobs (turn + push)
   [  B1  ] [  B2  ] [  B3  ]            ← 3 buttons
```

<p align="center">
  <img src="assets/encoders.svg" alt="The encoders and buttons of ichosynth with their gestures" width="720">
</p>

The gestures the firmware understands:

| Gesture | What it means |
|---|---|
| **Turn** (E1–E4) | change the value / move the cursor in the current context |
| **Short click** (push an encoder) | confirm / act (the meaning depends on the mode) |
| **Long press** (hold an encoder) | a second action (e.g. E1 hold = mute/subpattern) |
| **Tap a button** (B1/B2/B3) | the button's main function |
| **Hold a button** | the button's held function (e.g. B3 held = recording count-in) |
| **Combo B1+B2** | a shortcut — **the order you press them matters** (see ch. 11 & 12) |

> 💡 There is **no double-click**: the KY-040 encoders don't need one. Every action is a turn, a click, a
> hold, a button tap or a two-button combo.

What each encoder does changes with the mode. Here is the overview (details in the relevant chapters):

| Mode | E1 turn | E2 turn | E3 turn | E4 turn |
|---|---|---|---|---|
| **DRAW** | Y / note (row) | page | quick channel filter | X / column |
| **SINGLE** | channel | note (pitch) | — | X / column |
| **FILTER** | slider 1 | slider 2 | slider 3 | slider 4 |
| **MENU** | — | value | value | navigate menu pages |
| **VELOCITY** | velocity | probability | channel volume | condition / timing |
| **SONG** | — | pattern | — | position (1–64) |

The most useful encoder **clicks** (in DRAW/SINGLE):

- **E3 click** = **Play / Pause**.
- **E1 long-press** = enter mute / subpattern (release to restore).
- **E1 click @ row 16** (in SINGLE) = NOTE SHIFT.
- **E4 click** = confirm / enter a sub-menu.
- **E1 click** (in MENU) = back / exit.

---

## 3 · Reading the grid and the OLED

- **Rows** = the voices (8 sample voices + 3 synth voices), each with its own **color** (see [ch. 13](#13--voice-colors-and-the-synth-voices)).
- **Columns** = the 16 steps of the current page.
- **Top row (status)**: page indicators and status lights (copy active, etc.). During Play the page indicators turn **green**.
- **Play playhead**: the highlighted column that advances as you play (the ▼ in the image above).

> 📟 The original TŒRN showed the live state through the **colour of the encoder rings**. Our build has no
> RGB rings, so the **OLED** shows the same information in plain text: **current channel, mode, transport
> (PLAY / REC / STOP), BPM, volume and page**. Glance at it any time to know exactly where you are.

---

## 4 · The 3 buttons (B1 B2 B3)

The three tact switches are the heart of the transport and navigation:

| Button | Main function | Also does… |
|---|---|---|
| **B1 · PLAY** | start playback; toggle **SINGLE**; exit other modes back to **DRAW** | **held at power-on** = clear the RAM (fresh start) |
| **B2 · MENU** | enter / exit the **Menu** and the sub-modes | exits a sub-mode back to DRAW/SINGLE |
| **B3 · REC** | **record** (tap or hold) | **PAUSE** during playback · **tap-tempo BPM** · hold **>300 ms** = recording **count-in** |

> 💡 **PLAY is B1** (a single tap), not an encoder gesture. **PAUSE is B3** while a song is running.

---

## 5 · DRAW mode (drawing)

This is the main screen, the default one, where you create patterns.

| Action | Gesture |
|---|---|
| 🧭 **Move the cursor** | turn **E1** (up/down, row/note) and **E4** (left/right, column) |
| 📄 **Change page** | turn **E2** |
| ✏️ **Add / change a note** | push on the cursor's spot (you hear it right away); pressing again on a note cycles the voice |
| ▶️ **Play / Pause** | **E3 click** (Pause during play is also **B3**) |
| 🎚️ **Quick filter the channel** | turn **E3** to soften/brighten the voice under the cursor on the fly |
| 🔇 **Mute / subpattern** | **hold E1** (release to restore) |

> 💡 E3 is the "transport" knob in DRAW: **click** it for Play/Pause, **turn** it to nudge the current
> channel's filter without leaving the grid.

---

## 6 · Pages, patterns and subpatterns

- The grid shows **one page** (16 steps) at a time; turn **E2** to move between pages.
- Pages with notes are played in sequence on a loop to form a **pattern**. Patterns are chained in
  [SONG mode](#17--song-mode).
- **Subpatterns**: **hold E1** to drop into a momentary variation of the current pattern, then release to
  snap back — great for live fills and breaks.
- **Note copy / paste and note-shift** let you move and duplicate steps; the active copy/note-shift state
  shows on the grid's top row (and on the OLED).

---

## 7 · Mute (silencing voices)

- Put the cursor on a voice and **hold E1** to mute it / drop into its subpattern; release to restore.
- Muted channels are shown **on the grid itself**, so you can always see what's silent at a glance.

---

## 8 · Volume and BPM

- **Volume** and **BPM** are always readable on the **OLED**.
- **Tap-tempo**: tap **B3 (REC)** in time to set the **BPM** by ear.
- The per-channel **volume** is adjusted in [VELOCITY mode](#9--velocity-probability-and-conditions) with **E3**.

---

## 9 · Velocity, probability and conditions

TŒRN gives every step more than just on/off. In **VELOCITY** mode the four knobs become per-step controls:

| Knob | Controls |
|---|---|
| **E1** | **velocity** (how loud the step is) |
| **E2** | **probability** (chance the step fires) |
| **E3** | **channel volume** |
| **E4** | **condition / timing** (e.g. play every Nth pass, micro-timing) |

Use **B2 (MENU)** to step through the sub-modes; **B1 (PLAY)** returns you to DRAW.

---

## 10 · SINGLE mode (one voice only)

Useful for working in detail on one sample (e.g. a melody across several pitches).

- **Enter / exit SINGLE**: tap **B1 (PLAY)** to toggle SINGLE for the focused voice.
- In SINGLE: **E1 turn** = pick the **channel**, **E2 turn** = the **note (pitch)**, **E4 turn** = the **column (X)**.
- The same drawing/deleting gestures from DRAW apply, but only to the selected voice.

### Note Shift (in SINGLE)
- Put the cursor on row 16 and **click E1** to enter **NOTE SHIFT**, then move the notes with the knobs.

---

## 11 · FILTER mode and per-voice DSP

ichosynth has the full TŒRN per-voice DSP: a **lowpass filter**, **reverb**, **bitcrusher**, **detune**,
**octave**, and a **Moog ladder** on the synth voices.

- **Enter FILTER mode**: press **B2 + B1 together, with B2 first** (B2-first = FILTER MODE).
  This works on the channels that have filters (1–8, 11, 13–14).
- In FILTER mode the four knobs become **four sliders** (**E1 E2 E3 E4**) for the DSP of the selected
  voice. The OLED shows the selected filter and its value.
- Exit with **B2 (MENU)** or **B1 (PLAY)** back to DRAW.

> 💡 For a fast, no-mode tweak you can also just **turn E3 in DRAW** to filter the channel under the
> cursor. FILTER mode is for dialling in the full set of effects per voice.

---

## 12 · Changing the sample (Sample Browser)

To assign a different WAV to one of the 8 sample voices:

1. **Open the Sample Browser**: press **B1 + B2 together, with B1 first** (or both at once). This enters
   SET_WAV for channels 1–8.
2. **Navigate** with the knobs: change **folder** and **sample** (browse the SD); you can preview the
   **length** and **waveform**, and set **seek / length / reverse**.
3. **Confirm** with **E4 click** to load the selected sample onto the voice.
4. **Exit** with **B2 (MENU)**.

> 📁 Samples live on the microSD as `/samples/<folder>/_<number>.wav`
> (see the [build manual](BUILD_MANUAL.md)). WAVs should be mono, 16-bit, 44.1 kHz — `wavmaker.py`
> prepares them for you.

> ⏱️ **Order matters in the combo**: **B2 first** → FILTER MODE; **B1 first (or simultaneous)** → SAMPLE
> BROWSER. There is a short 350 ms cooldown between combos.

---

## 13 · Voice colors and the synth voices

Each voice has a fixed color (defined in [`colors.h`](colors.h)):

<p align="center">
  <img src="assets/voice-colors.svg" alt="Voice color legend: 1 red, 2 blue, 3 yellow, 4 green, 5 magenta, 6 lime, 7 orange, 8 turquoise, synth voices" width="540">
</p>

There are **8 sample voices** plus **3 synth voices**. The synth voices play internally generated waves
and follow the pitches of a scale; they have their own **Moog ladder** filter (set in [FILTER mode](#11--filter-mode-and-per-voice-dsp)).
TŒRN is **polyphonic**, so several voices sound together.

---

## 14 · Sample packs

A "sample pack" is a complete set of voices saved on the SD: recall a whole kit on the fly.

- Open the Sample Browser ([ch. 12](#12--changing-the-sample-sample-browser)) and use the pack controls
  to **load** a numbered pack onto the 8 sample voices.
- Packs let you swap an entire kit between songs without rebuilding it voice by voice.

> 📁 On the SD a pack is a numbered folder with its `.wav` files inside; ichosynth manages them, you don't
> need to create them by hand.

---

## 15 · Saving and loading (Menu)

- **Enter the Menu**: tap **B2 (MENU)**.
- Navigate the menu pages with **E4** (turn), adjust values with **E2 / E3**, and **confirm / enter a
  sub-menu with E4 click**; **E1 click = back**.
- From the Menu you **save** and **load** songs to/from the microSD.
- **Exit** the Menu with **B2 (MENU)** again, or **B1 (PLAY)** to jump straight back to DRAW.

---

## 16 · Live recording (REC)

ichosynth records audio straight from its input into the current channel.

> 🔌 **The Line In jack is the default record source.** Connect an instrument, another synth, a field
> recorder or a mixer send to the **6.35 mm (1/4") MONO Line In** jack and you can sample it straight
> in — no menu setup needed (the take is a mono sample). See the **Connections** note at the top of the
> manual for the jacks.

1. Choose the **channel** to record into.
2. **Hold B3 (REC)** to record from the input (**MIC** or **LINE**, the default; the choice shows on the OLED).
3. **Hold B3 > 300 ms** to get a **count-in** first (4 beats at the current BPM), then recording starts on the beat.
4. Release **B3** to stop; the take is saved to the SD and loaded onto the channel, so it survives a reboot.

> 💡 **B3 is multi-purpose**: a quick tap is **tap-tempo** / **PAUSE during play**; a hold is **record**.
> The OLED's transport readout shows **REC** while you're recording.

---

## 17 · SONG mode

SONG mode chains your patterns into a full arrangement.

- In SONG mode: **E2 turn** = choose the **pattern**, **E4 turn** = the **position** in the song (1–64).
- Build the sequence of patterns, then **PLAY (B1)** runs the whole song.
- Mute states and the song position are shown **on the grid**, so you can follow the arrangement live.

---

## 18 · MIDI and tap-tempo

- **USB MIDI**: ichosynth is a **USB MIDI** device. Connected over USB it plays/receives MIDI with a
  computer or other gear.
- **Tap-tempo**: tap **B3 (REC)** in time to set the BPM by feel — no menu needed.

---

## 19 · Mode & command map

From DRAW (the main screen) you reach everything with knobs, buttons and the two combos:

<p align="center">
  <img src="assets/modes-map.svg" alt="Map of the modes and the gestures to reach them" width="720">
</p>

Legend: **E1–E4** = the four knobs (turn or click) · **B1/B2/B3** = the three buttons · "click" = short
press · "hold" = long press · "combo" = two buttons together (order matters).

| You want to… | Gesture |
|-------|-------|
| Move cursor up/down (row/note) | turn **E1** |
| Move cursor left/right (column) | turn **E4** |
| Change page | turn **E2** |
| Add / change a note | push on the cursor's spot |
| **Play / Pause** | **E3 click** (Pause also **B3**) |
| Quick-filter the current channel | turn **E3** (in DRAW) |
| Mute / subpattern (current voice) | **hold E1** |
| **PLAY** (transport) | **B1** |
| **MENU** (save/load, settings) | **B2** |
| **REC** / pause / tap-tempo | **B3** |
| Clear RAM (fresh start) | **hold B1 at power-on** |
| Enter/exit **SINGLE** | **B1** (toggle) |
| **Note Shift** (in Single) | **E1 click @ row 16** |
| **VELOCITY** (velocity/prob/vol/condition) | **B2** to reach it → **E1/E2/E3/E4** |
| **FILTER mode** (per-voice DSP) | **B2 + B1, B2 first** → sliders on **E1–E4** |
| **Sample Browser** (set WAV) | **B1 + B2, B1 first / together** → confirm **E4 click** |
| **Menu** confirm / enter sub-menu | **E4 click** · back = **E1 click** |
| Recording **count-in** | **hold B3 > 300 ms** |

> ⚠️ **The two combos differ only by order**: **B2 first** → FILTER mode; **B1 first (or both at once)** →
> Sample Browser. Wait ~350 ms between combos.

---

## 20 · Common problems

| Symptom | Fix |
|---|---|
| 🔇 **I don't hear anything** | check the volume/channel volume (OLED), that the voice isn't muted (**hold E1**), and that the sample exists on the SD in the right format |
| ▶️ **It won't start** | Play is **B1** (or **E3 click**); Pause during play is **B3** |
| ↩️ **A knob goes the wrong way** | it's a CLK/DT swap from the wiring stage (see the build manual) |
| 🚫 **The samples won't play** | wrong SD path/structure, or WAV not mono/16-bit/44.1 kHz → use `wavmaker.py` |
| 🤔 **A combo opened the wrong mode** | mind the order: **B2 first** = FILTER, **B1 first** = Sample Browser; wait ~350 ms and retry |
| 💾 **I want a fresh start** | **hold B1 at power-on** to clear the RAM; save songs to the SD from the Menu (B2) |
| ⏱️ **Sample length** | long samples with continuous looping are supported |

---

<div align="center">

Have fun! 🎶

*ichosynth runs **TŒRN** by SP_ (soundpauli) · [toern.live](https://toern.live) · on a Teensy 4.1 with
4 KY-040 encoders, 3 tact switches and an SSD1306 OLED.*

</div>
