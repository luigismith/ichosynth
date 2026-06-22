# Mappa di controllo — TŒRN su hardware ichosynth (4 encoder + 3 pulsanti)

> Fase 1 del port: come i comandi fisici economici (4 encoder KY-040 con push +
> 3 tact switch) pilotano il firmware reale di TŒRN. Ricavata dall'analisi del
> sorgente `emulator/toern-src/` (23.442 righe). Le voci marcate **[conferma]**
> vanno verificate dal vivo nell'emulatore (ora ha i comandi a schermo).

## 1. Layout fisico e mappatura al firmware

```
   [ E1 ]   [ E2 ]   [ E3 ]   [ E4 ]      ← 4 encoder KY-040 (ruota + premi)
   [  B1  ] [  B2  ] [  B3  ]             ← 3 tact switch (i 3 "touch" di TŒRN)
```

| Comando fisico | Indice firmware | Sorgente TŒRN |
|---|---|---|
| E1 (sinistra) | encoder 0 (I2C 0x01, senso invertito `DIRE_LEFT`) | toern.ino:1048 |
| E2 | encoder 1 (0x41) | toern.ino:1049 |
| E3 | encoder 2 (0x20) | toern.ino:1050 |
| E4 (destra) | encoder 3 (0x61) | toern.ino:1051 |
| B1 | SWITCH_1 (pin **25** nel port) | toern.ino:159 |
| B2 | SWITCH_2 (pin **26** nel port) | toern.ino:160 |
| B3 | SWITCH_3 (pin **28** nel port) | toern.ino:161 |

> **Port (firmware reale sul nostro hardware):** i SWITCH_1/2/3 originali (pin 2/3/4)
> collidono con i pin che TŒRN usa internamente, quindi `teensy/build_toern.py` li
> rimappa a **25/26/28** (i 3 tact switch). Anche gli encoder evitano i pin riservati
> di TŒRN: **E4 = 37/38/39** (non i 4/2/3 di default). Il cablaggio dei pulsanti è
> **attivo-basso**: un lato al pin, l'altro a **GND** (`FastTouch.h` usa `INPUT_PULLUP`).
> Il percorso TTP223 su pin 5/22 è disattivo (`exttouch=false`), quindi non tocca E1.
> Mappa pin completa e definitiva in `teensy/README.md`.

## 2. Vocabolario dei gesti (cosa serve davvero)

TŒRN usa un set di gesti **semplice**, tutto gestito in software:

- **Ruota** (E1–E4) — cambia il valore/posizione del contesto.
- **Click corto** (E1–E4 push) — `buttons[i]=1`. (FSM in toern.ino:1334-1440)
- **Pressione lunga** (tieni premuto) — `buttons[i]=2` mentre tenuto, `=9` al rilascio.
- **Tap pulsanti** (B1/B2/B3) — azione momentanea (rising-edge).
- **Tieni B3 (>300 ms)** — count-in registrazione (toern.ino:1907).
- **Combo B1+B2** — l'ordine conta (vedi §4).
- **Doppio-click hardware: NON usato** (`writeDoublePushPeriod(0)`, toern.ino:3033).
  → Il KY-040 va benissimo: nessun doppio-click da emulare.

## 3. I tre pulsanti (B1/B2/B3) — funzioni precise

Sono la sostituzione 1:1 dei 3 touch capacitivi (agente confermato con file:riga).

| | Funzione principale | Note |
|---|---|---|
| **B1** (SWITCH_1) | **PLAY** (in y=1) · toggle **SINGLE** · esci-verso-DRAW da altri modi | toern.ino:4468-4500. Tenuto al boot = CLR RAM (EEPROM) |
| **B2** (SWITCH_2) | **MENU** entra/esci · esce dai sotto-modi tornando a DRAW/SINGLE | toern.ino:4530-4670 |
| **B3** (SWITCH_3) | **REC** (tap o tieni) · **PAUSE** (in y=1 durante play) · **tap-tempo BPM** · CLIC trigger | toern.ino:1874-1951, 4234-4335 |

## 4. Combo (due pulsanti insieme)

| Combo | Azione | Sorgente |
|---|---|---|
| **B1+B2**, B2 premuto per primo | entra in **FILTER MODE** (canali con filtri: 1-8, 11, 13-14) | toern.ino:4386-4430 |
| **B1+B2**, B1 premuto per primo / simultanei | entra in **SAMPLE BROWSER** (SET_WAV, canali 1-8) | toern.ino:4386-4430 |

> Cooldown 350 ms tra una combo e la successiva. Sul touchscreen serve il
> multi-touch (l'emulatore lo gestisce con gli eventi finger).

## 5. Encoder — rotazione e click per modalità

Schema generale (i dettagli fini vanno confermati dal vivo — **[conferma]**):

| Modo | E1 ruota | E2 ruota | E3 ruota | E4 ruota |
|---|---|---|---|---|
| **DRAW** | Y / nota | pagina (edit) | filtro rapido del canale **[conferma]** | X / colonna |
| **SINGLE** | canale | nota (pitch) | — **[conferma]** | X / colonna |
| **FILTER** | slider 1 | slider 2 | slider 3 | slider 4 (toern_filterUI.ino:265) |
| **MENU** | — | valore | valore | naviga pagine menu |
| **VELOCITY** | velocity | probabilità | volume canale | condizione/timing |
| **SONG** | — | pattern | — | posizione (1-64) |

Click encoder più importanti (in DRAW/SINGLE):

| Gesto | Azione | Sorgente |
|---|---|---|
| **E3 click** | Play/Pause | toern.ino:2011 |
| **E1 pressione lunga** | entra MUTE/SUBPATTERN (tieni) → rilascia = ripristina | toern.ino:2023-2038 |
| **E1 click @ y=16** (single) | NOTE SHIFT | toern.ino:2046 |
| **E4 click** | conferma / entra sotto-menu | toern.ino:2155 |
| **E1 click** (in MENU) | indietro / esci | toern.ino:2079 |

## 6. Cosa si sposta dagli anelli RGB all'OLED

TŒRN comunica lo stato col **colore degli encoder**; noi (senza RGB) lo mostriamo
sull'**OLED 128×64** — che TŒRN nemmeno ha. Info da portare su OLED:

| Info (era colore encoder) | Dove finisce | Sorgente |
|---|---|---|
| **Canale corrente** (E1/E4) | OLED: `CH:5` + colore sulla griglia | toern.ino:1723, 4213 |
| **Volume** durante overlay (E2) | OLED: barra + numero | toern.ino:1524, 4088 |
| **MIC vs LINE** in registrazione (E2) | OLED: testo `MIC`/`LINE` | toern.ino:3989, 4024 |
| **Filtro selezionato** (E3) in FILTER | OLED: nome + Hz | toern.ino:1773-1787 |
| Copypaste/Noteshift attivo | griglia 16×16 (riga 16) o OLED | toern_ui.ino:926 |
| Mute canali / posizione song | **già sulla griglia** (nessun lavoro) | — |

**FATTO (2026-06-19):** HUD OLED implementato come libreria `teensy/libraries/IchosOled`
(driver SSD1306 minimale, tutto in FLASHMEM/PROGMEM → ~80 byte di RAM1, perché TŒRN
lascia solo ~700 byte di RAM1 liberi e Adafruit_GFX/U8g2 lo farebbero traboccare).
Mostra **canale corrente, modo, stato trasporto (PLAY/REC/STOP), BPM, volume, pagina**.
`build_toern.py` lo aggancia da solo (include + `ichosOledBegin()` in setup +
`ichosOledRender(...)` nel loop, letti dai globali `GLOB`/`SMP`/`currentMode`).
Da fare in futuro (opzionale): MIC/LINE in registrazione e nome filtro in FILTER MODE.

## 7. Verifica nell'emulatore

L'emulatore ora ha i comandi a schermo (mouse/touch): 4 manopole (anello = ruota,
centro = premi) e i pulsanti B1/B2/B3 (+ FILT per il build NI404). Serve a confermare
le voci **[conferma]** e a provare la navigabilità reale prima di toccare l'hardware.
Tasti equivalenti: Q/A W/S E/D R/F = ruota, Z X C V = premi, 1 2 3 = B1/B2/B3.

## 8. Firmware di fallback NI404 (riferimento storico)

> ⚠️ **Questa sezione NON descrive il prodotto.** Il prodotto è il firmware reale di
> TŒRN (sezioni 1-7, build con `teensy/build_toern.py`). Qui sotto è documentato il
> vecchio firmware-banco basato su NI404 (`config.h` + `soundpauli_ni404.ino`), tenuto
> solo come fallback/riferimento. **I suoi pin sono diversi** da quelli del port (vedi
> §1 e `teensy/README.md`): qui valgono i pin del fork, non quelli definitivi.

Nel firmware NI404 di fallback (`config.h` + `soundpauli_ni404.ino`):
- **4 encoder** (`HAS_ENCODER4 1`): 4° encoder su pin **32/33** (CLK/DT), pulsante **41**.
- **Filtro alla TŒRN ("fast filter")**: in DRAW/SINGLE la **rotazione del 4° encoder**
  regola il cutoff lowpass della voce sotto il cursore — niente pulsante dedicato; la
  manopola si sincronizza al valore del canale quando il cursore cambia voce. Il 4°
  encoder è contestuale (filtro in draw/single, volume in VOLUME/BPM, seek nel browser).
- **3 pulsanti** su pin **24/25/26** (`BTN_SW1/2/3`, `BUTTONS3_ENABLED`):
  **B1=PLAY** (play/pausa), **B2=MENU** (entra/esci menu), **B3=REC**.
- **Registrazione** (`RECORD_ENABLED`): tieni **REC** → registra dall'ingresso del
  codec (`AudioInputI2S`+`AudioRecordQueue`) nel canale corrente; OLED mostra `*REC*`.
- Cablaggio pulsanti: un lato al pin, l'altro a **GND** (INPUT_PULLUP, attivi-bassi).

- **Bitcrusher + Moog ladder per-voce** (`BITCRUSH_ENABLED`, `LADDER_ENABLED`): primi due
  effetti TŒRN portati, inseriti nel grafo (filtro→crush→ladder→mixer) sulle 8 voci
  campione, default trasparenti. Verificati col `--play`. Manca solo il **controllo
  on-device** (non c'è un encoder libero in draw → serve la FX mode).

- **FX MODE** (`FXMODE_ENABLED`): **tieni MENU** → le 4 manopole diventano slider della
  voce sotto il cursore (E1 cutoff, E2 ladder cutoff, E3 ladder risonanza, E4 bitcrush),
  4 barre sulla griglia; tap MENU per uscire. È il controllo on-device degli effetti.

- **Registrazione salvata su SD** (`saveRecording`): al rilascio di REC la presa viene
  scritta in `samples/9/_9NN.wav` e caricata sul canale → persiste al riavvio.
- **Count-in REC**: tieni REC → 4 beat a tempo (4-3-2-1 sulla griglia, come l'ON1 di
  TŒRN) → poi registra. Basato su `millis()` nel loop (a `SMP.bpm`).

Verificato (PLAY, MENU, REC, manopole, filtro 4° encoder, bitcrusher + ladder, FX MODE,
salvataggio registrazione via `--play`). Da fare: count-in, e altri effetti (reverb —
serve lo shim freeverb + architettura di send).
