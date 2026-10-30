# 🖥️ Emulator

Runs the ichosynth firmware on Windows or macOS, with the 16×16 LED grid, the OLED, audio,
keyboard/mouse controls and MIDI controllers. Useful to try things without the hardware.
· *Esegue il firmware di ichosynth sul computer: griglia LED, OLED, audio, controlli e MIDI.*

```sh
python emulator/run.py            # the real TŒRN firmware (toernemu)
python emulator/run.py --bench    # the NI404-based bench firmware (ni404emu)
```

Ready-made Windows and macOS builds come from CI:
[emulator-latest](https://github.com/luigismith/ichosynth/releases/tag/emulator-latest).

📖 Full manual (Italian): [MANUALE.md](MANUALE.md) · state of the TŒRN target:
[STATUS-toern.md](STATUS-toern.md) · bench target: [STATUS.md](STATUS.md)
