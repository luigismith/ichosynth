# 🎚️ wavmaker

Prepares the micro-SD and converts any WAV to the format the firmware loads: **mono, 16-bit,
44100 Hz**. · *Prepara la micro-SD e converte qualsiasi WAV nel formato giusto.*

| File | What |
|---|---|
| `wavmaker.exe` | the app (Windows): scans the SD, creates the folders, finds the next free pack number, formats FAT32 if needed (removable SD cards only, never fixed disks) |
| `wavmaker_gui.py` | the source of the app (Python + tkinter, standard library only) |
| `wavmaker.py` | command line: `python tools/wavmaker/wavmaker.py <folder>` converts in place, `--pack 6 <folder>` builds pack 6 from up to 8 WAVs; with no folder it works on [`sdcard/`](../../sdcard) |
| `build_samples.py` | rebuilds the factory sample set in [`sdcard/`](../../sdcard) from the public-domain *drum_sklad* collection |

Card layout and sample licence: [`sdcard/README.md`](../../sdcard/README.md).
