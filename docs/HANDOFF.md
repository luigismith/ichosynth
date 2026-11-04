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
  driver `firmware/libraries/i2cEncoderLibV2` (re-implementa l'API Duppa).
- **3 tact switch** (PLAY/MENU/REC) al posto dei 3 sensori capacitivi —
  driver `firmware/libraries/FastTouch` (`fastTouchRead` su `INPUT_PULLUP`).
- **OLED SSD1306 I²C** al posto del feedback a colori degli anelli RGB —
  driver `firmware/libraries/IchosOled` (HUD: canale / modo / trasporto / BPM /
  volume / pagina). Tutto in FLASHMEM/PROGMEM → ~80 byte di RAM1.
- Nessun PCB (tutto a fili). La 2ª striscia LED reattiva di TŒRN è rimossa
  (libera il pin 24).

Le **feature sono quelle complete di TŒRN**: 8 voci campione + 3 voci synth,
polifonia, effetti per voce (reverb/bitcrusher/Moog ladder/detune/ottava), griglia
16×16→32×16, pagine, sotto-pattern, song mode, velocity/probabilità/condizioni,
mute, note-shift/copia-incolla, sample pack + browser SD, seek/length/reverse,
load/save su SD, registrazione dal vivo (MIC/LINE + count-in), MIDI DIN su Serial8 (pin 34/35,
circuito opzionale; il firmware non gestisce MIDI via USB), tap-tempo.

L'**NI404** originale di SP_ (da cui il repo era partito come fork) resta solo come
fallback/riferimento.

Strumenti companion (Windows, Python+tkinter, exe PyInstaller, sviluppati da Luigi):
- **`tools/wavmaker/wavmaker.exe`** — converte WAV in mono/16-bit/44.1k e **prepara la
  SD**: scansiona, capisce la struttura, deduce il prossimo numero libero, crea
  la struttura, e (se serve) formatta FAT32 — solo schede SD rimovibili, mai
  dischi fissi/di sistema. Numero pack, categoria e "cartella locale invece della
  SD" si scelgono nel pannello destinazione (non c'è una sezione "Avanzate").
- **`tools/flasher/flasher.exe`** — flasha il firmware sul Teensy **in un clic**, con
  un **loader HID puro-Python integrato** (`teensy_native.py`): niente Teensyduino,
  niente binari esterni. Spedisce il firmware ichosynth precompilato.

Stato hardware: il **firmware reale di TŒRN compila e linka** per il nostro Teensy
4.1 con i driver KY-040/FastTouch; **HUD OLED** completo; **mappa pin senza
collisioni**; 2ª striscia LED rimossa.

---

## 2. Mappa del repo (file chiave)

| Percorso | Cosa |
|---|---|
| `firmware/build_toern.py` | compila TŒRN → `firmware/build/toern.hex` (arduino-cli + core teensy:avr) |
| `firmware/build/toern.hex` | firmware ichosynth (TŒRN) compilato |
| `firmware/libraries/i2cEncoderLibV2` | driver dei 4 encoder KY-040 |
| `firmware/libraries/FastTouch` | driver dei 3 tact switch (PLAY/MENU/REC) |
| `firmware/libraries/IchosOled` | driver OLED SSD1306 (HUD di stato) |
| `firmware/README.md` | doc del port (mappa pin, build, perché -O1, OLED) |
| `emulator/toern-src/` | sorgenti TŒRN (clonati da github.com/soundpauli/toern) |
| `docs/reference/MAPPA_CONTROLLI.md` | come encoder/pulsanti pilotano TŒRN |
| `docs/reference/FEATURE_INVENTORY.md` | catalogo funzioni |
| `tools/wavmaker/wavmaker_gui.py` + `wavmaker.exe` | preparazione SD + conversione WAV |
| `tools/flasher/flasher_gui.py` + `teensy_native.py` + `flasher.exe` | flasher autonomo |
| `docs/wiring/CABLAGGIO.pdf` | **guida illustrata al cablaggio** (generata da `docs/wiring/make_cablaggio.py`, pin letti dai driver) |
| `case/` | **case stampato 3D** (3 pezzi, 2 piatti Kobra S1): generatore `build_case.py`, verifiche `check_fit.py`, render Blender + guida grafica `MONTAGGIO.pdf`, progetti Anycubic Slicer Next (`make_slicer_project.py`) |
| `docs/manuals/` | manuali IT/EN (.md + .pdf, rigenerati da `tools/pdf/build-pdfs.mjs`) |
| `docs/workshop/` | materiali del workshop ICHOS 2026 |
| `sdcard/` | contenuto della micro-SD (pack 0–5 + libreria `samples/`) |
| `legacy/` | NI404 di SP_: firmware-banco (usato dal target `ni404emu` dell'emulatore), PCB e case originali |
| `assets/` | diagrammi SVG (`_gen_assets.py`), illustrazioni del cablaggio, banner e anteprima social (`_make_banner.py`) |

---

## 3. Build & flash (promemoria)

- **Build firmware:** `python firmware/build_toern.py` → `firmware/build/toern.hex`.
  Serve `arduino-cli` su PATH + core `teensy:avr` (≥ 1.61.0). I sorgenti TŒRN sono
  attesi in `emulator/toern-src/` (lo script li clona se mancano). Dettagli in
  `firmware/README.md`.
- **`-O1` obbligatorio (`opt=o1std`):** al default `-O2` il gcc del Teensy **crasha**
  compilando la singola translation unit da ~23k righe di TŒRN (esce `0xffffffff`,
  errore interno / out-of-memory). Da Arduino IDE: **Tools → Optimize → "Fast"** (= -O1).
- **PSRAM:** TŒRN usa ~16,5 MB → servono **entrambi i chip** (16 MB) saldati,
  altrimenti il firmware non parte.
- **Pin remap del build:** `build_toern.py` riscrive i `#define SWITCH_1/2/3`
  (default 2/3/4, in collisione con E4) sui pin dei tact switch; aggancia anche
  l'OLED (`ichosOledBegin()` in setup + `ichosOledRender(...)` nel loop).
- **Flash:** usa `tools/flasher/flasher.exe` → premi il pulsante **PROGRAM** sul Teensy
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
(`INPUT_PULLUP`, attivi-bassi). Vedi `firmware/README.md` e `docs/reference/MAPPA_CONTROLLI.md`.

## 5. Struttura SD

```
SD (FAT32)
├── 0/  1.wav … 8.wav      ← samplepack 0 (kit di fabbrica), 8 voci
├── 1/  1.wav … 8.wav      ← samplepack 1 … fino a 99/
├── …
└── samples/               ← libreria del browser (SET_WAV), nomi liberi
    ├── kick/  …  snare/  …  hat/  …  perc/  …
```
Layout TŒRN: pack = `<pack>/1.wav..8.wav`; browser = `samples/<categoria>/<nome>.wav`.
Tutto **WAV mono / 16-bit / 44100 Hz**. `wavmaker` scrive in entrambi (vedi `sdcard/README.md`).
La vecchia convenzione NI404 `samples/<bank>/_<n>.wav` non è più usata.

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

## 7. Come riprendere su un altro PC (per esempio da casa)

Il repo su GitHub è l'unica fonte: tutto quello che serve per lavorare è lì. Su questo PC
restano solo file rigenerabili (build, render PNG grezzi, cache) e la vecchia distinta
base di giugno (`docs/files.zip`, ignorata da git perché superata).

**Prima volta su un computer nuovo**

1. `git clone https://github.com/luigismith/ichosynth.git` (dove vuoi; sul PC di lavoro
   è `D:\ichosynth`). Le volte dopo basta `git pull` **prima di iniziare** e
   `git commit` + `git push` **prima di chiudere**: così l'altro computer trova tutto.
2. Setup in un colpo (firmware + Python del case + strumenti PDF), si può rilanciare:
   - Windows: `powershell -ExecutionPolicy Bypass -File tools\setup-dev-env.ps1`
   - macOS / Linux: `tools/setup-dev-env.sh`

   Serve prima `arduino-cli` (`winget install ArduinoSA.CLI` · `brew install arduino-cli`).
   Su macOS, se `pip` rifiuta di installare ("externally managed"), crea un ambiente:
   `python3 -m venv .venv && source .venv/bin/activate`, poi rilancia lo script.
3. Programmi esterni, solo per quello che ti serve:

   | Per | Serve | Dove lo cercano gli script |
   |---|---|---|
   | firmware | `arduino-cli` + core `teensy:avr` ≥ 1.61 | PATH o `~/bin` |
   | case: STL, verifiche | Python ≥ 3.11 + `case/requirements.txt` | — |
   | progetti slicer (`.3mf`) e `--verifica` | Anycubic Slicer Next 2.0 | `C:\Program Files\AnycubicSlicerNext`, `/Applications/AnycubicSlicerNext.app`, oppure `ICHOS_SLICER=…` (il percorso su Mac non è ancora stato provato) |
   | render | Blender ≥ 4.2 | Windows `render.ps1`; macOS/Linux `render.sh` (`/Applications/Blender.app`, PATH o `BLENDER=…`) |
   | PDF (guide, manuali) | Chrome o Edge, Node per i manuali | percorsi soliti Windows/macOS, PATH o `CHROME=…` |
   | emulatore | MSYS2/MinGW + SDL2, o Homebrew su Mac | vedi `emulator/MANUALE.md` |

4. I sorgenti TŒRN (`emulator/toern-src/`, non nel repo) li clona `build_toern.py` se mancano.

**Claude Code sull'altro computer.** Apri Claude Code nella cartella del repo e digli di
leggere `docs/HANDOFF.md`: questo file contiene lo stato e le decisioni (sezioni 8 e 9),
quindi non serve copiare la memoria di Claude da un PC all'altro. La nota del progetto nel
second brain (OneDrive) è un riassunto in più, aggiornato la sera dal PC di lavoro.

**Controlli da lanciare dopo una modifica**

```sh
python case/build_case.py && python case/check_fit.py   # STL + interferenze (exit 1 se qualcosa non va)
python case/mutation_test.py                            # le verifiche si accorgono dei difetti? (tutte OK)
python case/make_slicer_project.py --verifica           # progetto PLA + slicing headless (anche --petg)
python tools/checklinks.py                              # link e ancore dei .md
```

---

## 8. Stato al 2026-11-04

- **Firmware**: compila e linka; nessuna delle correzioni del 30/10 (pulsanti in PULLUP,
  SD, EEPROM, OLED) è ancora provata sull'hardware.
- **Case**: Luigi ha stampato e montato un primo prototipo (zona comandi alta 21,5 mm). Era
  troppo basso: i pettini maschi lunghi, saldati su **tutta** la lunghezza del Teensy con i
  fili in cima, toccavano l'OLED e sollevavano il pannello. Versione attuale (commit
  `3e9349a`, render rifatti in `b883e1b`): zona comandi **28,5 mm** (+7 mm, scelta di Luigi
  "così è sicuro"), scritte incise più grandi, jack LINE IN tondo fino a Ø20, finestra
  dell'OLED 25 × 12,5 spostata di 1 mm verso i pin, OLED 3 mm a destra del centro (pin
  lontani dal pin 41 del Teensy). **Non ancora ristampata.**
- **Release v1.0** su GitHub: STL, `.3mf` e `MONTAGGIO.pdf` già sostituiti con la versione
  a 28,5 mm.

## 9. Decisioni e vincoli (non rimetterli in discussione senza Luigi)

- Root del repo pulita: solo README, README.it, LICENSE. Niente cartelle `_QUALCOSA`.
- Case: minimo numero di pezzi; matrice più bassa dei comandi; encoder 2×2 (E2 E3 sopra,
  E1 E4 sotto); OLED sopra gli encoder; tasti flessibili ricavati nel pannello; PLAY e MENU
  vicini. La scheda audio **appoggia sul Teensy** (in mezzo solo la plastica dell'header).
- **PLA e PETG non si attaccano**: due progetti slicer, ognuno tutto di un materiale.
- Il pannello si stampa **capovolto**: le scritte stanno sul piatto, quindi vanno grandi
  (≥ 4 mm, tratto ≥ 0,7 mm) o il primo strato le chiude.
- Render Blender e slicing sempre a **priorità bassa e con pochi thread** ("non impallare il
  pc"); per modifiche piccole non si rifanno i render.
- Le cartelle dati dello slicer in AppData non si toccano (solo lettura).

## 10. Prossimi passi

- [x] **Pin 41 sotto l'OLED** (2026-11-04): il pin GND dell'OLED stava 2 mm sopra la punta
  del pin 41 del Teensy (SW di E2, con filo saldato). OLED spostato di 3 mm a destra
  (`OLED_C` = (32, 122)): ora 2,7 mm, e `check_fit` vuole almeno 2,5. I render mostrano
  ancora l'OLED centrato.
- [ ] **Ristampare il case** a 28,5 mm e provare il montaggio (pettini lunghi, jack tondo).
- [ ] A schermo acceso, controllare che la finestra dell'OLED non tagli l'immagine
  (`OLED_WIN`, `OLED_WIN_DY` in `case/build_case.py`).
- [ ] **Guida al cablaggio e manuali**: dicono "14 pin per lato"; il prototipo ha i pettini
  su tutto il Teensy. Allineare, e aggiungere le avvertenze sull'OLED: fili saldati sui pin e
  piegati subito in orizzontale, niente connettori Dupont.
- [ ] **Distinta base** aggiornata nel repo (quella di giugno ha 3 encoder, case in legno e
  Dupont).
- [ ] **Verifica on-hardware:** flash e conferma direzione encoder, polarità pulsanti
  e combo come da `docs/reference/MAPPA_CONTROLLI.md`.
- [ ] Rifinire l'HUD OLED (MIC/LINE in registrazione, nome filtro in FILTER mode).
- [ ] Prima di ristampare ancora, misurare sui componenti veri: matrice (160 mm), punte dei
  pin sopra il Teensy (`HDR_PIN_UP` = 10,9), posizione del jack cuffie sulla Rev D
  (`AUDIO_JACK_DX`), switch 4,3 mm; provare la sensazione dei tasti flessibili
  (`TAB_T`, `NUB_GAP`).
