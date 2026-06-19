# ichosynth — Handoff / come riprendere il progetto

> Documento per riprendere il lavoro su un altro PC (o in una nuova sessione di
> Claude Code) senza perdere il contesto. Lo stato del **codice** è interamente
> su GitHub: `git clone` e hai tutto.

Repo: **https://github.com/luigismith/ichosynth** (branch `master`).
Progetto: **ichosynth** — una **build a basso costo di TŒRN** (il groovebox di
SP_/soundpauli, MIT, https://toern.live) su hardware saldato a mano, per il
workshop **ICHOS 2026** di Francesco Giannico a Taranto (12–14 giugno 2026).
Autore/manutentore: **Luigi Massari (luigismith)**. Documentario sonoro: Roberta Trani.

---

## 1. Cos'è e cosa è stato fatto

ichosynth fa girare il **firmware reale di TŒRN** su un **Teensy 4.1 + Audio Shield
(SGTL5000) + matrice LED 16×16**, sostituendo i componenti costosi dell'originale
con parti economiche e saldabili:

- **4 encoder KY-040** (ruota + premi) al posto dei 4 encoder I²C RGB Duppa —
  driver `teensy/libraries/i2cEncoderLibV2` (re-implementa l'API Duppa).
- **3 tact switch** (PLAY/MENU/REC) al posto dei 3 sensori capacitivi —
  driver `teensy/libraries/FastTouch` (`fastTouchRead` su `INPUT_PULLUP`).
- **OLED SSD1306 I²C** al posto del feedback a colori degli anelli RGB —
  driver `teensy/libraries/IchosOled` (HUD: canale / modo / trasporto / BPM /
  volume / pagina). Tutto in FLASHMEM/PROGMEM → ~80 byte di RAM1.
- Nessun PCB (tutto a fili). La 2ª striscia LED reattiva di TŒRN è rimossa
  (libera il pin 24).

Le **feature sono quelle complete di TŒRN**: 8 voci campione + 3 voci synth,
polifonia, effetti per voce (reverb/bitcrusher/Moog ladder/detune/ottava), griglia
16×16→32×16, pagine, sotto-pattern, song mode, velocity/probabilità/condizioni,
mute, note-shift/copia-incolla, sample pack + browser SD, seek/length/reverse,
load/save su SD, registrazione dal vivo (MIC/LINE + count-in), USB-MIDI, tap-tempo.

L'**NI404** originale di SP_ (da cui il repo era partito come fork) resta solo come
fallback/riferimento.

Strumenti companion (Windows, Python+tkinter, exe PyInstaller, sviluppati da Luigi):
- **`_SDCARD/wavmaker.exe`** — converte WAV in mono/16-bit/44.1k e **prepara la
  SD**: scansiona, capisce la struttura, deduce il prossimo numero libero, crea
  la struttura, e (se serve) formatta FAT32. Override sotto "Avanzate".
- **`_FLASHER/flasher.exe`** — flasha il firmware sul Teensy **in un clic**, con
  un **loader HID puro-Python integrato** (`teensy_native.py`): niente Teensyduino,
  niente binari esterni. Spedisce il firmware ichosynth precompilato.

Stato hardware: il **firmware reale di TŒRN compila e linka** per il nostro Teensy
4.1 con i driver KY-040/FastTouch; **HUD OLED** completo; **mappa pin senza
collisioni**; 2ª striscia LED rimossa.

---

## 2. Mappa del repo (file chiave)

| Percorso | Cosa |
|---|---|
| `teensy/build_toern.py` | compila TŒRN → `teensy/firmware/toern.hex` (arduino-cli + core teensy:avr) |
| `teensy/firmware/toern.hex` | firmware ichosynth (TŒRN) compilato |
| `teensy/libraries/i2cEncoderLibV2` | driver dei 4 encoder KY-040 |
| `teensy/libraries/FastTouch` | driver dei 3 tact switch (PLAY/MENU/REC) |
| `teensy/libraries/IchosOled` | driver OLED SSD1306 (HUD di stato) |
| `teensy/README.md` | doc del port (mappa pin, build, perché -O1, OLED) |
| `emulator/toern-src/` | sorgenti TŒRN (clonati da github.com/soundpauli/toern) |
| `_DOCS/MAPPA_CONTROLLI.md` | come encoder/pulsanti pilotano TŒRN |
| `_DOCS/FEATURE_INVENTORY.md` | catalogo funzioni |
| `_SDCARD/wavmaker_gui.py` + `wavmaker.exe` | preparazione SD + conversione WAV |
| `_FLASHER/flasher_gui.py` + `teensy_native.py` + `flasher.exe` | flasher autonomo |

---

## 3. Build & flash (promemoria)

- **Build firmware:** `python teensy/build_toern.py` → `teensy/firmware/toern.hex`.
  Serve `arduino-cli` su PATH + core `teensy:avr` (≥ 1.61.0). I sorgenti TŒRN sono
  attesi in `emulator/toern-src/` (lo script li clona se mancano). Dettagli in
  `teensy/README.md`.
- **`-O1` obbligatorio (`opt=o1std`):** al default `-O2` il gcc del Teensy **crasha**
  compilando la singola translation unit da ~23k righe di TŒRN (esce `0xffffffff`,
  errore interno / out-of-memory). Da Arduino IDE: **Tools → Optimize → "Fast"** (= -O1).
- **PSRAM:** TŒRN usa ~16,5 MB → servono **entrambi i chip** (16 MB) saldati,
  altrimenti il firmware non parte.
- **Pin remap del build:** `build_toern.py` riscrive i `#define SWITCH_1/2/3`
  (default 2/3/4, in collisione con E4) sui pin dei tact switch; aggancia anche
  l'OLED (`ichosOledBegin()` in setup + `ichosOledRender(...)` nel loop).
- **Flash:** usa `_FLASHER/flasher.exe` → premi il pulsante **PROGRAM** sul Teensy
  quando richiesto. (Il reboot software in bootloader è inaffidabile su Windows:
  il pulsante è la via certa.)

---

## 4. Mappa pin (la "verità" del firmware)

KY-040 `{CLK, DT, SW}`:

| Encoder | CLK | DT | SW |  | Pulsanti | Pin |
|---|---|---|---|---|---|---|
| E1 | 5 | 22 | 15 |  | PLAY | 25 |
| E2 | 32 | 33 | 41 |  | MENU | 26 |
| E3 | 9 | 14 | 16 |  | REC | 28 |
| E4 | 37 | 38 | 39 |  | | |

LED DIN = 17 · OLED+codec I²C SDA=18 / SCL=19. Pulsanti: l'altro capo a GND
(`INPUT_PULLUP`, attivi-bassi). Vedi `teensy/README.md` e `_DOCS/MAPPA_CONTROLLI.md`.

## 5. Struttura SD

```
SD (FAT32)
└── samples/
    ├── 0/  _1.wav … _99.wav      (bank = numero // 100)
    ├── 1/  _100.wav … _199.wav
    └── …
<pack>/<slot>.wav   ← pack-canzone (li crea lo strumento al salvataggio)
```
wavmaker scrive esattamente in `samples/<bank>/_<n>.wav`.

---

## 6. Gotcha / lezioni apprese

- **PSRAM:** servono i **2 chip** (TŒRN ~16,5 MB); senza, non parte.
- **Board nuda (senza SD) si riavvia ogni ~8–15s**: è il loop che interroga lo slot
  SD vuoto; con una SD inserita sparisce. Non è un bug.
- **`-O2` crasha il compilatore** → usare `-O1` (`opt=o1std` / "Fast").
- **"Device descriptor request failed" (VID_0000/PID_0002)** = cavo/porta USB, non firmware.
- **Reboot software in HalfKay inaffidabile su Windows** → pulsante PROGRAM.
- **Gli .exe non sono firmati** → SmartScreen al primo avvio ("Ulteriori informazioni → Esegui comunque").

---

## 7. Come riprendere su un altro PC

1. **Codice:** `git clone https://github.com/luigismith/ichosynth.git` (idealmente
   nello stesso percorso `D:\NI404-main` per coerenza con gli strumenti).
2. **Sorgenti TŒRN:** se manca `emulator/toern-src/`, lo clona `build_toern.py`,
   oppure `git clone --depth 1 https://github.com/soundpauli/toern.git emulator/toern-src`.
3. **Toolchain:** `arduino-cli` + core `teensy:avr` (per il firmware); per
   l'emulatore vedi `emulator/MANUALE.md` (MSYS2/MinGW + SDL2, o Homebrew su Mac).
4. **Memoria di Claude (contesto tra sessioni):** copia la cartella
   `~/.claude/projects/D--NI404-main/memory/` sul nuovo PC nello stesso percorso.
5. **Chat (facoltativo):** copia anche il transcript `.jsonl` dalla stessa cartella.
6. Apri Claude Code nella cartella del repo: con questo `_HANDOFF.md` + la memoria,
   il contesto è recuperato.

---

## 8. Prossimi passi

- [ ] **Verifica on-hardware:** flash e conferma direzione encoder, polarità pulsanti
  e combo come da `_DOCS/MAPPA_CONTROLLI.md`.
- [ ] Allineare il firmware spedito dal flasher all'ultimo `toern.hex`.
- [ ] Rifinire l'HUD OLED (MIC/LINE in registrazione, nome filtro in FILTER mode).
