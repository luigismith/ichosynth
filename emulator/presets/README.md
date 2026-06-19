# ichosynth emulator — MIDI controller setup (MPK Mini mk2/mk3/mk4/Plus & others)

The emulator can be driven by a MIDI controller (both targets: the default
`ni404emu` bench firmware and the `toernemu` TŒRN reference). Because each
controller — and even each MPK Mini revision — sends **different CC numbers** for
its knobs, the mapping is **configurable at runtime** and **self-discovering**, so
it works with any model (including the **MPK Mini mk4 / MPK Mini IV**, whose factory
knob CCs differ from the mk3).

## The mapping (coherent 1:1)

| Control on the MPK Mini | ichosynth action              |
|-------------------------|-------------------------------|
| **Knob 1 / 2 / 3 / 4**  | turn **encoder 1 / 2 / 3 / 4**|
| **Pad 1 / 2 / 3 / 4**   | **push** encoder 1 / 2 / 3 / 4|
| Pad 5 / 6               | cursor Y+ / Y−                |
| Pad 7 / 8               | cursor X+ / X−                |
| Keys (keybed)           | play / record current sample  |

So **knob N turns encoder N and pad N presses it** — one coherent pair per encoder.

## Making your controller match (the important part)

The knob CC numbers are read from **`midi-map.txt`** (created automatically next to
the exe on first run). Defaults are mk3-style `70,71,72,73`. If your knobs feel
wrong/incoherent (e.g. on the **mk4**), do this:

1. Run the emulator and **turn each knob / hit each pad**.
2. Look at the **console** (run from PowerShell: `./run.ps1 toernemu`) **or** open
   **`midi-log.txt`** (next to the exe). Every message is logged, e.g.:
   ```
   [midi] CC   ch=1  #74 = 64      <- this knob's CC is 74
   [midi] Note ch=1  40 vel=120    <- this pad's note is 40
   ```
3. Edit **`midi-map.txt`**: put your four knob CCs (K1,K2,K3,K4) and eight pad
   notes, then **restart** the emulator:
   ```
   knobs=70,71,72,73
   pads=36,37,38,39,40,41,42,43
   monitor=1
   ```

That's it — no rebuild needed. (Tell me your numbers and I can also bake a model
default in.)

## Notes
- Knobs are read as **absolute** (0–127) and converted to relative encoder motion.
  If your knobs are set to *relative/increment* mode in the Akai editor, switch them
  to **absolute/CC**.
- Keys (notes outside the pad range) are played by the firmware (chromatic sample
  play/record on the selected channel).
- The mapping lives in `src/midi_map.cpp` if you want to change the actions.
