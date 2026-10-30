# ⚡ Flasher

Loads the ichosynth firmware onto the Teensy 4.1 **in one click**. No Arduino, Teensyduino or
other tools to install: the Teensy loader is built in.
· *Carica il firmware di ichosynth sul Teensy 4.1 **con un clic**, senza installare nulla.*

1. Download **`flasher.exe`** (here, or from the
   [latest release](https://github.com/luigismith/ichosynth/releases/latest)) and run it.
   Windows may warn that the app is unsigned: *More info → Run anyway*.
2. Connect the Teensy with a **data** USB cable.
3. Press **⚡ Flash ichosynth** and, when asked, the white **PROGRAM** button on the Teensy.

| File | What |
|---|---|
| `flasher.exe` | the app (Windows, built with PyInstaller from `flasher_gui.py`) |
| `ichosynth.hex` | the firmware it ships: TŒRN built by [`firmware/build_toern.py`](../../firmware/build_toern.py) |
| `flasher_gui.py` | the source of the app (Python, standard library + tkinter) |
| `teensy_native.py` | the built-in pure-Python Teensy 4.1 HID loader |

The `.hex` is checked (checksums and end of file) before it is written. On Windows the board is
not rebooted by software, because that is unreliable there: the PROGRAM button always works.
To flash a firmware you built yourself, choose `firmware/build/toern.hex` with **Sfoglia…**, or run
`python firmware/build_toern.py --flash`.
