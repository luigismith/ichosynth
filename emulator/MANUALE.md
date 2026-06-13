# Emulatore NI404 / TŒRN — Manuale utente

Emulatore desktop (Windows e macOS) del sequencer/sampler **SP_ NI404** (Teensy 4.1
+ Audio Shield). Esegue il **firmware reale** ricompilato in modo nativo: la stessa
logica che gira sull'hardware, ma sul computer, con la griglia LED 16×16, il display
OLED, l'audio e i controlli su tastiera/mouse e controller MIDI.

Sono inclusi **due programmi**:

| Programma | Cosa esegue |
|---|---|
| `ni404emu` | Il firmware **NI404** (il tuo fork) + il display OLED SSD1306 |
| `toernemu` | Il firmware **TŒRN** completo + HUD OLED |

---

## 1. Avvio rapido

### Windows
1. Apri la cartella `emulator\playable-2026-06-13\` (oppure `emulator\build\`).
2. Doppio clic su **`ni404emu.exe`** (o `toernemu.exe`).
   - Tutto il necessario è già lì accanto (`SDL2.dll` e le altre librerie).
3. Si apre la finestra con la griglia LED in alto e il display OLED in basso.

Per far partire subito un brano dimostrativo:
```
ni404emu.exe --demo
```

### macOS
Il binario macOS va generato su un Mac (vedi §10). Una volta compilato:
```
./build/ni404emu            # avvio normale
./build/ni404emu --demo     # con la demo
```

> L'emulatore legge i campioni da `C:\NI404-main\_SDCARD` (su Mac: la cartella
> `_SDCARD` del repository). Non spostarla.

---

## 2. La finestra

- **In alto**: la **griglia LED 16×16** (la stessa matrice WS2812 dell'hardware).
  Mostra il pattern del sequencer, i numeri, i menu del firmware.
- **In basso**: il **display OLED 128×64** (lo status HUD: modo corrente, BPM,
  volume, velocity, pagina, play/stop).

L'orientamento della griglia rispecchia il pannello fisico (riga 1 in basso).

---

## 3. Controlli da tastiera del PC

I 4 encoder, i loro pulsanti e gli ingressi extra sono mappati sulla tastiera:

| Tasto | Funzione |
|---|---|
| **Q / A** | Encoder 1 (sinistro) — ruota indietro / avanti |
| **W / S** | Encoder 2 (centrale) — ruota indietro / avanti |
| **E / D** | Encoder 3 (destro) — ruota indietro / avanti |
| **R / F** | Encoder 4 — ruota indietro / avanti |
| **Z** | Premi encoder 1 |
| **X** | Premi encoder 2 |
| **C** | Premi encoder 3 |
| **V** | Premi encoder 4 |
| **B** | Pulsante FILTRO (solo NI404) |
| **1 / 2 / 3** | Touch 1 / 2 / 3 (solo TŒRN) |
| **TAB** | Apre/chiude il **menu impostazioni** |
| **Esc** | Esci |

> **Niente reagisce ai tasti?** Clicca prima sulla **finestra grafica**: se il focus
> è sulla finestra console (quella con i log), la tastiera va lì. Poi ripremi.

---

## 4. Menu impostazioni (TAB)

Premi **TAB** per sovrapporre il menu. Navighi con le **frecce**:

- **↑ / ↓** — scegli la voce
- **← / →** — cambia il valore della voce selezionata
- **TAB** o **Esc** — chiudi

Voci:

| Voce | Cosa fa |
|---|---|
| **Audio output** | Sceglie la scheda/uscita audio (← → per scorrere i dispositivi) |
| **Master volume** | Guadagno d'uscita 0×…64× (alza qui se senti basso) |
| **Audio input** | Sceglie l'ingresso (per futuri usi di registrazione) |
| **MIDI input** | Mostra i controller MIDI rilevati |
| **MIDI map** | Ricorda dove si configura la mappatura (`midi-map.txt`) |
| **Keyboard** | Legenda dei tasti |
| **Close** | Chiude il menu |

Le impostazioni si salvano in **`settings.txt`** accanto all'eseguibile.

---

## 5. Audio

- Uscita predefinita del sistema all'avvio; cambiala dal menu (TAB → Audio output).
- Se senti **troppo piano**, alza **Master volume** nel menu (fino a 64×) oppure il
  volume interno dello strumento (encoder sinistro in modo BPM/VOL).
- La demo è tarata con un po' di headroom (picco ~0,9, niente clipping).

---

## 6. Controller MIDI

Collega un controller USB-MIDI **prima** di avviare l'emulatore: all'avvio apre
**tutte** le porte MIDI di ingresso (alcuni controller, come l'MPK mini IV, mettono
le manopole su una seconda porta).

### Preset incluso: Akai MPK mini IV (mk4)
Già mappato e pronto:
- **Manopole 1–4** → Encoder 1–4 (sono encoder *relativi*, CC 24–27)
- **Pad 1–4** → premono gli encoder 1–4
- **Pad 5–8** → navigazione griglia (X± / Y±)
- **Tastiera** → suona il campione del canale selezionato (vedi §7)

### Configurazione: `midi-map.txt`
Alla prima esecuzione viene creato `midi-map.txt` accanto all'eseguibile. È un file
di testo, modificabile, riletto al riavvio:

```
knobs=24,25,26,27        # i 4 CC delle manopole -> encoder 1..4
knobmode=relative        # 'relative' (encoder mk4) oppure 'absolute' (potenziometri mk3/Plus: 70..73)
pads=36,37,38,39,40,41,42,43   # le 8 note dei pad
notevelocity=110         # velocity fissa per note/pad che suonano un campione (0 = dinamica reale)
monitor=1                # registra il MIDI in arrivo su console + midi-log.txt
```

> **Non sai i numeri del tuo controller?** Lascia `monitor=1`, avvia l'emulatore,
> muovi manopole e premi i pad: ogni messaggio compare in console e in
> **`midi-log.txt`**. Copia i numeri giusti nel file e riavvia.

Per **altre MPK mini** (mk2/mk3/Plus) con manopole a potenziometro:
```
knobs=70,71,72,73
knobmode=absolute
```

---

## 7. Suonare i campioni con la tastiera MIDI

Lo strumento suona **il campione del canale attualmente selezionato** (la riga su
cui si trova il cursore, `SMP.y`):

1. **Seleziona il canale**: porta il cursore sulla riga del campione che vuoi
   suonare (con gli encoder, come sull'hardware).
2. **Suona la tastiera MIDI**: il **DO centrale (nota 60)** è l'intonazione base del
   campione; i tasti più alti/bassi lo **traspongono** di semitoni.
3. Suona un canale per volta (quello selezionato). Per suonare un altro suono,
   sposta il cursore su un'altra riga.

Se il sequencer è in **play**, le note suonate vengono anche **registrate** nello
step corrente (come sull'hardware).

### I pad come pulsanti (velocity disattivata)
Per impostazione predefinita **la velocity è fissa** (`notevelocity=110`): qualunque
nota/pad suona il campione sempre allo stesso volume — i pad si comportano da
**pulsanti**, non sono sensibili alla dinamica. Per riattivare la dinamica reale
metti `notevelocity=0` in `midi-map.txt`.

---

## 8. La demo (`--demo`)

`ni404emu.exe --demo` fa partire un brano di **4 pagine (64 step) in loop** che mostra
tutte le potenzialità:

- progressione di accordi **Am – F – C – G** (una per pagina);
- arrangiamento che cresce: intro → groove → apice → fill di chiusura;
- **8 campioni** ritmici/percussivi + **2 voci sintetizzate** (basso sawtooth e lead
  triangolare) con vere melodie;
- **pitch dei campioni per riga**, **filtro per-canale** udibile, **dinamica di
  velocity**, a **122 BPM**.

Premi **Esc** per uscire.

---

## 9. SD card e campioni

I campioni vivono in **`_SDCARD/`**, che fa da scheda SD virtuale, con la struttura
attesa dal firmware:

```
_SDCARD/
  0/ 1/ 2/ 3/ ...        # cartelle/pacchetti
  3/_300.wav .. _311.wav # il kit della demo (16-bit mono 44.1 kHz)
  autosaved.txt          # pattern salvato automaticamente
  settings.txt           # impostazioni dell'emulatore
```

- I file sono WAV **16-bit mono 44.1 kHz** con header standard.
- Puoi gestire/creare la struttura con **`wavmaker`** (in `_SDCARD/`).
- Il kit della demo è generato da `emulator/scripts/gen_samples.cpp`.

> **Nota sui salvataggi:** all'avvio il firmware ricarica `autosaved.txt`. Un file di
> salvataggio vecchio o corrotto con valori di filtro a 0 chiuderebbe i filtri (audio
> quasi muto): il firmware ora **sanifica** i valori fuori range (filtri riaperti).

---

## 10. Compilare dai sorgenti

L'emulatore **ricompila il sorgente** del firmware (non esegue il `.hex`): servono il
codice e il toolchain.

### Windows (MSYS2 + MinGW)
```powershell
cd emulator\scripts
.\bootstrap-windows.ps1     # installa toolchain + SDL2 (una volta)
.\build.ps1                 # configura, compila, copia le DLL accanto all'exe
.\run.ps1                   # avvia
```
Build manuale:
```powershell
$env:PATH="C:\msys64\mingw64\bin;$env:PATH"
cmake -S emulator -B emulator/build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build emulator/build
```

### macOS (Homebrew + clang)
```bash
cd emulator/scripts
./bootstrap-macos.sh        # installa Xcode CLT + cmake + sdl2 (una volta)
./build.sh                  # configura e compila ni404emu (+ toernemu)
./build/ni404emu            # avvia
```
Il `CMakeLists.txt` è già multipiattaforma: su macOS collega i framework **CoreMIDI**
/ **CoreFoundation**; su Windows usa **winmm** e linka staticamente il runtime MinGW.

### Verifiche headless (senza finestra)
```
ni404emu --selftest    # boot + loop + audio + LED + MIDI di prova
ni404emu --verify      # carica i WAV dalla SD e prova gli 8 canali
ni404emu --demotest    # renderizza l'intero loop della demo e riporta picco/clipping
```

---

## 11. Risoluzione problemi

| Sintomo | Causa / Rimedio |
|---|---|
| Audio troppo basso | Alza **Master volume** (TAB) o il volume interno; controlla che `autosaved.txt` non sia un salvataggio strano. |
| I tasti non fanno nulla | Clicca sulla **finestra grafica** per darle il focus (non sulla console). |
| Le manopole MIDI non rispondono | Controllo collegato prima dell'avvio; verifica `midi-map.txt` (CC e `knobmode`); guarda `midi-log.txt`. |
| Pad sensibili al tocco | È previsto disattivarlo: `notevelocity=110` (pulsanti). Per la dinamica: `notevelocity=0`. |
| L'exe non parte (Windows) | Tieni `SDL2.dll` accanto all'eseguibile (nello snapshot c'è già). |
| Display capovolto | Già corretto: la griglia rispecchia il pannello fisico (riga 1 in basso). |

---

## 12. Limiti noti

- È un **ricompilatore sorgente**, non un emulatore di CPU/binario: serve il codice
  del firmware, non il `.hex`.
- Fedeltà DSP **molto vicina ma non campione-per-campione** identica all'hardware
  (filtro SVF, inviluppi, freeverb, voce di resampling sono reimplementazioni).
- Non è cycle-accurate (timing guidato dal callback audio + loop).
- Alcune funzioni sono ancora stub (registrazione mic/line-in, granular).
- Un firmware nuovo della stessa famiglia hardware può richiedere di estendere gli
  shim in `compat/` per le API che usa.

---

*Per dettagli di progetto e stato avanzamento: `emulator/STATUS.md` e
`emulator/STATUS-toern.md`.*
