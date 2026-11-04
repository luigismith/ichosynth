# 🛠️ tools

| Folder / file | What |
|---|---|
| [`flasher/`](flasher) | ⚡ one-click firmware flasher for the Teensy 4.1 (Windows app + the ready-made `.hex`) |
| [`wavmaker/`](wavmaker) | 🎚️ WAV converter and micro-SD preparation (Windows app + command line) |
| [`pdf/`](pdf) | 📄 rebuilds the manual PDFs in `docs/manuals/` from their Markdown |
| `setup-dev-env.ps1` · `setup-dev-env.sh` | 💻 installs the Teensy core and libraries, the Python packages of the case and the PDF tools, then compile-checks the firmware (Windows · macOS/Linux) |
| `checklinks.py` | 🔗 checks every relative link and `#anchor` in the repo's Markdown (exit 1 if one is broken) |
