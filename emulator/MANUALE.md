# Emulatore ichosynth — Manuale utente

Emulatore desktop (Windows e macOS) usato come **banco di prova** per ichosynth. Esegue
il firmware ricompilato in modo nativo sul computer, con la griglia LED 16×16, il display
OLED, l'audio, i controlli su tastiera/mouse/touch e i controller MIDI.

| Programma | Cosa esegue |
|---|---|
| `toernemu` | **Il firmware dello strumento**: il TŒRN reale, con le stesse patch e gli stessi driver che finiscono nel `.hex` — **target principale** |
| `ni404emu` | Il vecchio firmware-banco basato su NI404 (`legacy/soundpauli_ni404/`), tenuto come riferimento |

### Quanto è fedele `toernemu` all'hardware

- **Stessi sorgenti.** La build CMake prepara lo sketch con
  `firmware/build_toern.py --stage-only`, cioè lo stesso passo di staging e le stesse patch
  della build per il Teensy (pin dei pulsanti 25/26/28, `INPUT_PULLUP`, pull-up sul pin 2,
  SD nello slot del Teensy 4.1, ingresso LINE IN di default, seconda striscia LED tolta,
  aggancio dell'HUD OLED). Il commit di TŒRN è quello fissato in `build_toern.py`.
- **Stessi driver.** Si compilano i driver veri di `firmware/libraries/`: `i2cEncoderLibV2`
  (KY-040: senso `DIRE_LEFT` di E1, 4 conteggi per scatto, antirimbalzo 8 ms),
  `FastTouch` (pulsanti) e `IchosOled` (l'HUD, in un file a parte come sul Teensy).
- **Sotto ci sono modelli, non stub.** I pin ricordano il loro `pinMode` e i pulsanti sono
  "saldati" verso GND: un pulsante lasciato in `INPUT_PULLDOWN` risulta sempre premuto,
  come sulla scheda. Il bus I²C ha un SSD1306 che decodifica i byte veri (NACK se manca,
  buffer da 32 byte, tempo di trasferimento). La SD sta nello slot integrato. La memoria
  audio ha il tetto chiesto da `AudioMemory(n)`. I timer girano su un loro thread, come
  interrupt, non a ogni fotogramma.
- **Non è lo stesso codice macchina.** È un ricompilatore di sorgenti, non un emulatore di
  CPU: tempi e DSP sono vicini ma non identici al ciclo (vedi §12).

---

## 1. Avvio rapido

### Con il launcher (consigliato)

Dalla cartella del repository un solo comando compila (se serve, a priorità bassa: il PC
resta usabile) e avvia. Controlla che ci siano CMake, il compilatore, `mingw32-make`
(Windows) e SDL2, e se mancano dice cosa installare. Se mancano i sorgenti di TŒRN li
scarica al commit fissato (serve `git`).

```
python emulator/run.py                 # il firmware dello strumento (toernemu)
python emulator/run.py --bench         # il firmware-banco (ni404emu)
python emulator/run.py --rebuild       # ricompila da zero
python emulator/run.py --build-only    # compila soltanto
python emulator/run.py -- --no-sd      # quello che segue "--" va all'emulatore
python emulator/run.py -- --hwtest     # il test headless del comportamento dell'hardware
```

Per provare una variante del synth modifichi il firmware (o le patch in
`firmware/build_toern.py`) e rilanci `python emulator/run.py`: CMake rifà lo staging da
solo e ricompila. È la stessa variante che poi flashi con `python firmware/build_toern.py`.

### Windows (eseguibile già compilato)
1. Apri `emulator\build\` (o scarica lo zip della release
   [emulator-latest](https://github.com/luigismith/ichosynth/releases/tag/emulator-latest)).
2. Doppio clic su **`toernemu.exe`**. `SDL2.dll` è già lì accanto (la copia `run.py`).

### macOS
Il binario si genera su un Mac (vedi §10) o si scarica dalla release. Poi:
```
./toernemu            # il firmware dello strumento
./ni404emu --demo     # il firmware-banco con il brano dimostrativo
```

> Sul Mac **non c'è ingresso MIDI**: la build usa GCC (serve a compilare gli sketch Arduino)
> e le intestazioni CoreMIDI di Apple funzionano solo con Clang. Tastiera, mouse, audio,
> registrazione e drag-and-drop funzionano.

---

## 2. La finestra

Il titolo dice quale firmware gira: *ichosynth emulator - TŒRN firmware (toernemu)*.

- **In alto**: la **griglia LED 16×16** (la matrice WS2812). Riga 1 in basso, come sul
  pannello fisico.
- **Al centro**: il **display OLED 128×64**. Mostra esattamente quello che il driver
  `IchosOled` manda al display: `CH:` canale e trasporto (`STOP`, `>PLAY`, `*REC*`),
  `MODE:` modo di TŒRN, `BPM:`, `VOL:` e `PAGE:`. Si aggiorna una riga alla volta,
  come sul modulo reale. Per provare la scheda **senza OLED** avvia con la variabile
  d'ambiente `ICHOS_EMU_NO_OLED=1`: nessuno risponde all'indirizzo 0x3C e il firmware
  prosegue senza HUD.
- **In basso**: le 4 manopole **E1–E4** e i 3 pulsanti **B1/B2/B3** (PLAY / MENU / REC),
  usabili con mouse o dita (§3).

---

## 3. Controlli

I comandi fanno quello che fanno sullo strumento: li interpreta TŒRN. Qui c'è un riassunto
dei ruoli; la mappa completa, con i riferimenti al sorgente, è in
[`docs/reference/MAPPA_CONTROLLI.md`](../docs/reference/MAPPA_CONTROLLI.md).

### A schermo (mouse / touch)
- **Manopole**: trascina sul **bordo** per ruotare; **premi al centro** per premere
  l'encoder; premi al centro e trascina = tieni premuto e ruoti. Anche la rotellina del
  mouse sopra una manopola la ruota. Senso orario = un passo "+" del KY-040.
- **Pulsanti**: B1, B2, B3. Il multi-touch permette le combinazioni (B1+B2).

### Da tastiera del PC

| Tasto | Comando |
|---|---|
| **Q / A** · **W / S** · **E / D** · **R / F** | E1 · E2 · E3 · E4: ruota antiorario / orario |
| **Z · X · C · V** | premi E1 · E2 · E3 · E4 |
| **1 · 2 · 3** | pulsanti **B1 · B2 · B3** |
| **TAB** | menu impostazioni dell'emulatore |
| **Esc** | esci |

> Niente reagisce ai tasti? Clicca prima sulla finestra grafica per darle il focus.

### Cosa fanno (TŒRN)

| Comando | Funzione principale |
|---|---|
| **B1** | **PLAY** (sulla riga 1) · entra/esci **SINGLE** · torna a DRAW da altri modi. Tenuto all'accensione = CLR RAM (cancella la EEPROM) |
| **B2** | **MENU**: entra / esce; esce dai sotto-modi tornando a DRAW o SINGLE |
| **B3** | **REC** (tap o tieni) · **pausa** sulla riga 1 durante il play · tap-tempo |
| **B1+B2** | B2 premuto per primo = **FILTER MODE**; B1 per primo o insieme = **browser dei campioni** (SET_WAV) |
| **E1** | in DRAW: riga / nota (in senso orario il cursore **scende**, come impone `DIRE_LEFT`) |
| **E2** | in DRAW: pagina |
| **E3** | click = **Play / Pausa** |
| **E4** | in DRAW: colonna (orario = verso destra); click = conferma / entra |

In FILTER MODE le 4 manopole diventano 4 slider; nel menu E4 sfoglia le pagine ed E2/E3
cambiano i valori.

---

## 4. Menu impostazioni (TAB)

**TAB** apre il menu dell'emulatore (non quello di TŒRN). **↑ / ↓** sceglie la voce,
**← / →** cambia il valore, **TAB** o **Esc** chiude.

| Voce | Cosa fa |
|---|---|
| **Uscita audio** | sceglie la scheda/uscita audio |
| **Volume** | guadagno d'uscita 0×…64× |
| **Ingresso audio** | il dispositivo che fa da ingresso del codec (§9). Se ne scegli uno resta aperto (come l'ingresso della scheda: il livello d'ingresso di TŒRN funziona anche prima di registrare); con *(nessuno)* si apre l'ingresso predefinito solo durante una registrazione |
| **Cartella SD** | il percorso della SD; **Invio** la apre in Esplora file |
| **Ripristina SD** | **Invio** torna alla cartella SD predefinita |
| **Campioni SD** | in `toernemu` i campioni si scelgono da TŒRN (SET_WAV); nel banco apre il suo browser |
| **MIDI in** | i controller MIDI rilevati |
| **Mappa MIDI** | dove si configura la mappatura (`toernemu-midi-map.txt`) |
| **Tasti** | legenda dei tasti |

Le impostazioni si salvano accanto all'eseguibile in **`toernemu-settings.txt`**
(`ni404emu-settings.txt` per il banco).

---

## 5. Audio

- Come sul Teensy, l'audio parte **dopo** `setup()`: prima il firmware chiama
  `AudioMemory()` e costruisce il grafo, poi si apre l'uscita. La finestra invece è attiva
  da subito e mostra quello che `setup()` disegna (animazione di avvio, `SD?`).
- Il grafo ha a disposizione **esattamente i blocchi chiesti da `AudioMemory(n)`** (TŒRN:
  128). Se finiscono, i nodi perdono l'uscita come sull'hardware. `--hwtest` riporta l'uso
  massimo (circa 20 blocchi su 128).
- Filtri e inviluppi seguono gli algoritmi della Teensy Audio Library: il filtro di stato
  ha le uscite passa-basso, passa-banda e passa-alto (TŒRN le usa tutte e tre), il ladder
  segue l'ingresso di modulazione di frequenza (`octaveControl`), l'inviluppo ha i default,
  la fase *hold* e il rilascio forzato del Teensy.
- Se **non c'è un'uscita audio** (nessuna scheda, sessione remota o bloccata) il grafo
  continua a girare su un clock silenzioso, così ingresso, registrazione e inviluppi si
  comportano come sulla scheda.
- Volume troppo basso? Alza **Volume** nel menu (fino a 64×) o il volume di TŒRN.

---

## 6. Controller MIDI

Collega il controller USB-MIDI **prima** di avviare: l'emulatore apre **tutte** le porte
d'ingresso (alcuni controller, come l'MPK mini IV, mettono le manopole su una seconda
porta). Su macOS il MIDI non c'è (§1).

### Preset incluso: Akai MPK mini IV (mk4)
- **Manopole 1–4** → E1–E4 (encoder relativi, CC 24–27)
- **Pad 1–4** → premono E1–E4
- **Pad 5–8** → navigazione griglia
- **Tastiera** → arriva al firmware come MIDI in ingresso (USB MIDI di TŒRN)

### Configurazione: `toernemu-midi-map.txt`
Alla prima esecuzione viene creato **accanto all'eseguibile** (`ni404emu-midi-map.txt` per
il banco). È un file di testo modificabile, riletto al riavvio:

```
knobs=24,25,26,27        # i 4 CC delle manopole -> E1..E4
knobmode=relative        # 'relative' (encoder mk4) oppure 'absolute' (potenziometri mk3/Plus: 70..73)
pads=36,37,38,39,40,41,42,43   # le 8 note dei pad
notevelocity=110         # velocity fissa per le note (0 = dinamica reale)
monitor=1                # registra il MIDI in arrivo su console + toernemu-midi-log.txt
```

> Non sai i numeri del tuo controller? Lascia `monitor=1`, avvia, muovi manopole e pad:
> ogni messaggio compare in console e in `toernemu-midi-log.txt`.

Per altre MPK mini (mk2/mk3/Plus) con potenziometri: `knobs=70,71,72,73` e
`knobmode=absolute`.

---

## 7. Il firmware-banco (`ni404emu`)

Il vecchio firmware NI404 ha controlli suoi (descritti in §8 di
[`MAPPA_CONTROLLI.md`](../docs/reference/MAPPA_CONTROLLI.md)): 4° encoder = filtro rapido,
pulsante MENU tenuto = FX MODE, il canale suonato dalla tastiera MIDI è la riga del cursore
(DO centrale = intonazione base). Il suo browser dei campioni (TAB → Campioni SD) elenca i
file `_N.wav`. `ni404emu --demo` fa partire un brano di 4 pagine (Am – F – C – G, 8
campioni + 2 voci sintetizzate, 122 BPM).

Tre differenze rispetto a `toernemu`, volute perché quel firmware non le regge: la EEPROM
vergine vale 0x00 invece di 0xFF (con 0xFF non carica nessun samplepack), i suoi salvataggi
`*.txt` sulla SD hanno il suffisso `-ni404emu` (formato diverso da quello di TŒRN) e un
percorso `samples/<cartella>/_N.wav` cerca anche `<cartella>/_N.wav`.

---

## 8. Controlli headless (senza finestra)

| Comando | Cosa verifica |
|---|---|
| `toernemu --hwtest` | La scheda emulata come la userebbe una persona, su una copia temporanea della SD: avvio in DRAW e testo dell'HUD letto dal pannello, direzione di E1 ed E4, B2 = MENU, E3 = play/stop, tempo del sequencer (passi al secondo rispetto ai BPM), memoria audio, modello dei pin (PULLDOWN = sempre premuto), import di un WAV a 48 kHz stereo, registrazione da un tono sull'ingresso. Stampa PASS/FAIL e il codice d'uscita è il numero di fallimenti. Gira anche in CI. |
| `toernemu --selftest` | avvio, qualche `loop()`, LED, OLED, memoria audio |
| `toernemu --screenshot file.bmp [ms]` | apre la finestra vera, salva il suo contenuto dopo `ms` millisecondi dall'apertura (default 4000) ed esce |
| `ni404emu --verify` / `--demotest` / `--play` | i controlli del banco (8 canali, brano demo, suonarlo) |

---

## 9. SD card, campioni e registrazione

La cartella **`sdcard/`** del repository fa da micro SD (layout descritto in
[`sdcard/README.md`](../sdcard/README.md)):

```
sdcard/
  0/ 1/ … 5/             # samplepack: <pack>/1.wav … 8.wav (una voce per canale)
  samples/<categoria>/   # libreria del browser SET_WAV (kick, snare, hat, …)
  samples/import/        # i file importati dall'emulatore
  autosaved.txt          # salvataggio automatico di TŒRN (scritto dal firmware)
```

Formato dei campioni: WAV PCM **mono, 16 bit, 44.1 kHz**.

- La SD virtuale sta nello **slot integrato del Teensy 4.1**: un firmware che la cercasse
  sullo slot della scheda audio (`SD.begin(10)`) non la troverebbe, come sull'hardware.
- **`--no-sd`** simula lo slot vuoto: come sulla scheda vera TŒRN mostra **`SD?`** sulla
  griglia e aspetta. **Trascinare una cartella** sulla finestra equivale a inserire la
  scheda (anche TAB → Ripristina SD): TŒRN la trova e prosegue l'avvio.
- `FILE_WRITE` **accoda** come sul Teensy (TŒRN cancella i file prima di riscriverli).
- **Cambiare SD**: trascina una cartella sulla finestra; **TAB → Ripristina SD** torna a
  quella predefinita.
- L'emulatore **scrive davvero** nella cartella SD (salvataggi, registrazioni, import).
  Per non toccare `sdcard/` del repository trascina sulla finestra una sua copia.

### Importare campioni (WAV / MP3 / FLAC)
**Trascina un file audio nella finestra**: viene decodificato (decoder `dr_libs` integrati),
convertito in mono 16 bit 44.1 kHz e scritto in **`samples/import/<nome>.wav`** sulla SD
(nome in minuscolo, al massimo 60 caratteri, mai sovrascritto). Poi lo scegli da TŒRN con
il browser dei campioni (**B1+B2**, SET_WAV), come un file copiato sulla micro SD reale.

### Registrazione
L'ingresso del codec è il dispositivo scelto in **TAB → Ingresso audio**; il segnale passa
per la catena d'ingresso di TŒRN (amplificatore d'ingresso, meter, monitor) come sulla
scheda, ricampionato a 44.1 kHz qualunque sia la frequenza del dispositivo.

- In DRAW **tieni B3** sulla riga di un canale campione: registra finché tieni premuto e
  salva la ripresa sulla SD in **`0/<canale>.wav`** (il samplepack 0, quello delle
  registrazioni), poi la carica nel canale. Verificato con `--hwtest`.
- La registrazione dal modo REC del menu scrive **`samples/rec_NN.wav`** (o nella cartella
  del browser aperta).

Le registrazioni restano sulla SD dopo il riavvio.

> **Attenzione, MIC o LINE IN.** Su una EEPROM vergine (Teensy nuovo, o dopo CLR RAM)
> TŒRN scrive i propri default e mette l'ingresso su **MIC**, anche se `build_toern.py`
> imposta LINE IN: la patch vale solo per il valore iniziale della variabile. L'emulatore
> lo mostra (`--hwtest` stampa l'ingresso scelto). Sullo strumento, che non ha microfono,
> va scelto LINE IN dal menu di TŒRN finché il firmware non viene corretto.

### File di runtime
Accanto all'eseguibile, uno per target: `toernemu-settings.txt`, `toernemu-eeprom.bin`
(la EEPROM; se lo cancelli riparti da un Teensy nuovo, tutto a 0xFF),
`toernemu-midi-map.txt`, `toernemu-midi-log.txt`. Sulla SD: i file che scrive il firmware
(`autosaved.txt`, il backup delle impostazioni, le registrazioni). Sono tutti ignorati da
git.

---

## 10. Compilare dai sorgenti

L'emulatore ricompila i sorgenti del firmware (non esegue il `.hex`). Servono: CMake, un
compilatore C++17 (GCC), SDL2, Python 3 (per lo staging di TŒRN) e git (solo la prima
volta, per scaricare TŒRN).

### Windows (MSYS2 + MinGW64)
```powershell
cd emulator\scripts
.\bootstrap-windows.ps1     # installa gcc, cmake, make, SDL2 (una volta)
.\build.ps1                 # TŒRN al commit fissato, configura, compila entrambi, copia SDL2.dll
.\run.ps1                   # avvia toernemu (.\run.ps1 ni404emu per il banco)
```
Build manuale:
```powershell
$env:PATH="C:\msys64\mingw64\bin;$env:PATH"
python firmware/build_toern.py --fetch-only
cmake -S emulator -B emulator/build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build emulator/build
```
Entrambi i target sono configurati di default (`EMU_BUILD_TOERN=ON`); se mancano i sorgenti
di TŒRN, CMake salta `toernemu` con un avviso.

### macOS (Homebrew + GCC)
```bash
cd emulator/scripts
./bootstrap-macos.sh        # Xcode CLT + gcc, cmake, sdl2, python, dylibbundler (una volta)
./mac-build.sh              # compila toernemu + ni404emu e impacchetta in emulator/dist-macos/
```
Si usa **GCC di Homebrew**, non Clang: gli sketch Arduino richiedono `-fpermissive`. Per
questo la build macOS non ha MIDI in ingresso (CoreMIDI richiede Clang). Su Linux
`./build.sh` compila entrambi i target.

---

## 11. Risoluzione problemi

| Sintomo | Causa / rimedio |
|---|---|
| `run.py` dice che manca qualcosa | Segui il suggerimento che stampa (MSYS2, `bootstrap-windows.ps1`, SDL2, git). |
| Audio troppo basso | Alza **Volume** (TAB) o il volume di TŒRN. |
| Nessun suono, in console `failed to open audio device` | Nessuna uscita audio disponibile: il firmware gira lo stesso (clock silenzioso). Scegli un'uscita in TAB. |
| I tasti non fanno nulla | Clicca sulla finestra grafica per darle il focus. |
| Le manopole MIDI non rispondono | Controller collegato prima dell'avvio; verifica `toernemu-midi-map.txt` e guarda `toernemu-midi-log.txt`. Su macOS il MIDI non c'è. |
| L'exe non parte (Windows) | Tieni `SDL2.dll` accanto all'eseguibile (`run.py` e `build.ps1` la copiano). |
| Comportamento strano dopo tante prove | Cancella `toernemu-eeprom.bin` (Teensy nuovo) e `sdcard/autosaved.txt`. |
| In console `[gpio] … WARNING` | Un pin di un pulsante è configurato in un modo che la scheda vera non tollera (per esempio PULLDOWN): è un errore del firmware o di una patch. |

---

## 12. Limiti noti

- È un **ricompilatore di sorgenti**, non un emulatore di CPU: serve il codice, non il `.hex`.
- `loop()` gira su un suo thread a circa 700 giri al secondo (con 1 ms di pausa per non
  occupare un core); sul Teensy gira molto più veloce. I gesti temporizzati con `millis()`
  (antirimbalzo, pressioni lunghe) si comportano come sull'hardware, i tempi di esecuzione no.
- Gli interrupt dei timer e l'aggiornamento audio girano su thread veri, serializzati da un
  unico lock che `noInterrupts()` e `AudioNoInterrupts()` prendono; sul Teensy un interrupt
  sospende `loop()`, qui gira in parallelo fuori dalle sezioni critiche.
- DSP vicino ma non identico campione per campione: SVF e inviluppo seguono gli algoritmi
  Teensy in virgola mobile; ladder, freeverb e voce di resampling sono reimplementazioni.
- **Granular** e **AudioPlaySdWav** di TŒRN sono ancora stub (silenzio).
- I tempi del bus I²C sono stimati (9 clock per byte); i tempi della SD no.
- Un firmware nuovo della stessa famiglia può richiedere di estendere gli shim in `compat/`.

---

*Stato e storia del port: `emulator/STATUS-toern.md` (TŒRN) e `emulator/STATUS.md` (banco).*
