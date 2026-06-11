# ichosynth — Handoff / come riprendere il progetto

> Documento per riprendere il lavoro su un altro PC (o in una nuova sessione di
> Claude Code) senza perdere il contesto. Lo stato del **codice** è interamente
> su GitHub: `git clone` e hai tutto.

Repo: **https://github.com/luigismith/ichosynth** (branch `master`).
Progetto: **ichosynth** — fork a **3 encoder** di NI404 (SP_/soundpauli) per il
workshop **ICHOS 2026** di Francesco Giannico a Taranto (12–14 giugno 2026).
Autore/manutentore: **Luigi Massari (luigismith)**.

---

## 1. Cos'è e cosa è stato fatto

Sampler/sequencer su **Teensy 4.1 + Audio Shield (SGTL5000) + matrice LED 16×16
+ 3 encoder KY-040 + OLED**. È l'NI404 originale a 3 encoder, con in più:

- **OLED SSD1306** (HUD di stato) e **MIDI clock OUT** (sync master).
- **Filtro lowpass per-voce** (1 pulsante su **pin 41 → GND**): tieni premuto +
  gira la manopola CENTRALE = cutoff della voce sotto il cursore. Mappatura
  mutuata da TOERN (MIT). Attivabile/disattivabile con `FILTER_ENABLED` in `config.h`.
- Remap dei gesti del "4° encoder" mancante su 3 pulsanti (build a 3 encoder).
- **Repo bilingue** (IT/EN) con manuali + PDF + infografiche.

Strumenti companion (Windows, Python+tkinter, exe PyInstaller, sviluppati da Luigi):
- **`_SDCARD/wavmaker.exe`** — converte WAV in mono/16-bit/44.1k e **prepara la
  SD**: scansiona, capisce la struttura, deduce il prossimo numero libero, crea
  la struttura, e (se serve) formatta FAT32. Override sotto "Avanzate".
- **`_FLASHER/flasher.exe`** — flasha il firmware sul Teensy **in un clic**, con
  un **loader HID puro-Python integrato** (`teensy_native.py`): niente Teensyduino,
  niente binari esterni. Spedisce `ichosynth.hex` precompilato.

Stato hardware: firmware **compila, linka, flasha e fa boot** sul Teensy reale
(validato più volte). Test del **synth completo** (con SD + audio shield + LED)
ancora da fare.

---

## 2. Mappa del repo (file chiave)

| Percorso | Cosa |
|---|---|
| `soundpauli_ni404.ino` | firmware principale (main .ino) |
| `config.h` | switch di compilazione (HAS_ENCODER4 0, FILTER_ENABLED, BTN_FILTER 41, range filtro) |
| `display.h` / `audioinit.h` / `colors.h` / `files.h` | header del firmware |
| `MANUALE_COSTRUZIONE.md` / `BUILD_MANUAL.md` | guida build (IT/EN) |
| `MANUALE_USO.md` / `USAGE_MANUAL.md` | guida uso (IT/EN) |
| `MANUALE_AMBIENTE.md` / `DEV_ENVIRONMENT.md` | setup ambiente di sviluppo (IT/EN) |
| `scripts/setup-dev-env.ps1` / `.sh` | installer one-shot del toolchain |
| `assets/_gen_assets.py` / `_md2pdf.py` | generatori infografiche / PDF |
| `_SDCARD/wavmaker_gui.py` + `wavmaker.exe` | preparazione SD + conversione WAV |
| `_FLASHER/flasher_gui.py` + `teensy_native.py` + `flasher.exe` + `ichosynth.hex` | flasher autonomo |

---

## 3. Build & flash (promemoria)

- **Toolchain:** arduino-cli + core `teensy:avr` (1.60.x), **FastLED pinnato a 3.9.10**
  (le 3.10.x rompono il path WS2812Serial), librerie newdigate
  `teensy-variable-playback` + `teensy-polyphony` da **GitHub HEAD** (le copie del
  registry hanno API disallineate). Tutto automatizzato in `scripts/setup-dev-env.*`.
- **FQBN:** `teensy:avr:teensy41:usb=serialmidi16`.
- **Trucco compilazione:** la cartella di build deve chiamarsi come il main .ino
  (`soundpauli_ni404`); il repo si chiama diversamente, quindi copia i sorgenti
  in una cartella `soundpauli_ni404` e compila con `--build-path`.
- **`#include "config.h"` va DOPO `#include <FastLED.h>`** (altrimenti i template
  param di FastLED vengono clobberati).
- **Flash:** usa `_FLASHER/flasher.exe` → premi il pulsante **PROGRAM** sul Teensy
  quando richiesto. (Il reboot software in bootloader è inaffidabile su Windows:
  il pulsante è la via certa.)

---

## 4. Struttura SD (verificata contro NI404 ufficiale)

```
SD (FAT32)
└── samples/
    ├── 0/  _1.wav … _99.wav      (bank = numero // 100)
    ├── 1/  _100.wav … _199.wav
    └── … fino a bank 9
<pack>/<slot>.wav   ← pack-canzone (li crea il synth al salvataggio)
<n>.txt             ← pattern/song
```
`maxFolders = 9`, `maxFiles = 9`. wavmaker scrive esattamente in `samples/<bank>/_<n>.wav`.

---

## 5. Gotcha / lezioni apprese

- **Board nuda (senza SD) si riavvia ogni ~8–15s, senza CrashReport**: è `drawNoSD()`
  che interroga lo slot SD vuoto; con una SD inserita sparisce. Non è un bug del fork.
- **"Device descriptor request failed" (VID_0000/PID_0002)** = cavo/porta USB, non firmware.
- **`serialprint`/`serialprintln` sono no-op**: il firmware non stampa nulla salvo `CrashReport`.
- **Reboot software in HalfKay inaffidabile su Windows** → pulsante PROGRAM.
- **Gli .exe non sono firmati** → SmartScreen al primo avvio ("Ulteriori informazioni → Esegui comunque").

---

## 6. Come riprendere su un altro PC

1. **Codice:** `git clone https://github.com/luigismith/ichosynth.git` (idealmente
   nello stesso percorso `D:\NI404-main` per coerenza con gli strumenti).
2. **Toolchain:** lancia `scripts/setup-dev-env.ps1` (Windows) o `.sh` (macOS/Linux).
3. **Memoria di Claude (contesto tra sessioni):** copia la cartella
   `~/.claude/projects/D--NI404-main/memory/` sul nuovo PC nello stesso percorso.
4. **Chat (facoltativo):** copia anche il transcript `.jsonl` dalla stessa cartella
   `~/.claude/projects/D--NI404-main/`.
5. Apri Claude Code nella cartella del repo: con questo `_HANDOFF.md` + la memoria,
   il contesto è recuperato.

---

## 7. Da chiudere / prossimi passi

- [ ] Test del synth completo su hardware (SD con sample pack + audio shield + LED).
- [ ] **Dispense per i corsisti** (workshop).
- [ ] **Presentazione + appunti di insegnamento** per il docente.
