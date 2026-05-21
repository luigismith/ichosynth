# NI404 — Manuale di Costruzione (versione DIY, senza PCB stampato)

Guida passo-passo, pensata per chi è alle prime armi, per costruire un NI404
**cablato a mano** (hard-wired), cioè senza il PCB custom del progetto. Tutti i
collegamenti si fanno con fili volanti (jumper) seguendo le tabelle dei pin.

> Il NI404 è un campionatore-sequencer open-source basato su Teensy 4.1. Genera
> tutti i suoni da solo, non serve un computer per suonare (il computer serve
> solo per programmarlo la prima volta).

---

## 1. Cosa stai costruendo

- Un cervello: **Teensy 4.1** (un microcontrollore potente).
- Una scheda audio (**Teensy Audio Adaptor**) con uscita cuffie da 3,5 mm.
- Un display di gioco: una **matrice LED RGB 16x16** (256 LED).
- Tre o quattro **manopole rotative con pulsante** (encoder KY-040).
- Una **micro SD** dove stanno i campioni audio e i tuoi pattern.
- (Opzionale, aggiunta di questo fork) un piccolo **schermo OLED** che mostra
  modalità, BPM, volume, ecc.

Tutto viene alimentato dalla porta **USB (5V)**.

---

## 2. Livello di difficoltà — leggi prima di comprare

Onestà prima di tutto:

- Il cablaggio di matrice ed encoder è **facile** (sono saldature grosse e
  collegamenti a filo): adatto a un principiante paziente.
- La parte **difficile** è saldare i due chip **PSRAM** sul retro del Teensy
  4.1: sono componenti SMD minuscoli. Se non hai mai saldato SMD:
  - opzione A (consigliata): compra il Teensy 4.1 **con la PSRAM già saldata**,
    oppure fattela saldare da chi ha esperienza/stazione ad aria calda;
  - opzione B: esercitati prima su schede di pratica.
- La PSRAM **è obbligatoria**: il firmware usa ~16 MB di memoria esterna
  (servono **due** chip da 8 MB). Senza, non parte.

Tempo stimato: mezza giornata per chi sa già saldare; di più se è la prima
volta.

---

## 3. Lista componenti (BOM)

| Q.tà | Componente | Note |
|------|------------|------|
| 1 | Teensy 4.1 | il microcontrollore principale |
| 2 | Chip PSRAM 8 MB (APS6404, formato compatibile Teensy 4.1) | totale 16 MB, **obbligatori** |
| 1 | Teensy Audio Adaptor Board, **Rev D (per Teensy 4.x)** | codec audio SGTL5000 + jack 3,5 mm + slot SD (non usato) |
| 1 | Matrice LED **WS2812B 16x16** (256 LED) | rigida o flessibile |
| 3–4 | Encoder rotativo **KY-040** con pulsante | 4 = versione completa; 3 = versione ridotta |
| 1 | Micro SD Card, **Class 10**, ≤ 32 GB | formattata **FAT32** |
| 1 | Cavo micro-USB + alimentatore 5V (≥ 2A consigliato) | alimentazione e programmazione |
| 1 | Cuffie con jack 3,5 mm | il NI404 non ha altoparlanti |
| q.b. | Cavetti jumper Dupont (~10 cm), strip di pin header | per i collegamenti |
| 1 | (opzionale, fork) OLED **SSD1306 0,96" 128x64 I2C** | schermo informazioni |
| 1 | (opzionale) Contenitore stampato 3D | file STL in `_DOCS/_ENCLOSURE/` |

> Nota licenze campioni: il progetto **non** include file audio. Userai i tuoi
> campioni (vedi capitolo 9).

---

## 4. Strumenti necessari

- Saldatore a punta fine + stagno (e flussante, molto utile per la PSRAM).
- Tronchesino, spelafili, pinzette.
- "Terza mano" o morsa per tenere fermi i pezzi.
- Multimetro (per controllare continuità e cortocircuiti — fondamentale).
- Alcol isopropilico per pulire i residui di flussante.
- Precauzioni antistatiche (braccialetto ESD): il Teensy e la PSRAM sono
  sensibili.
- (Solo se saldi tu la PSRAM) stazione ad aria calda o saldatore di precisione.

---

## 5. Concetti base di sicurezza

1. **Mai** collegare/scollegare fili mentre il dispositivo è alimentato.
2. Doppio controllo **GND e 5V/3,3V** prima di dare corrente: invertirli può
   bruciare i componenti.
3. Dopo ogni fascio di saldature, col multimetro in modalità continuità
   verifica che **non** ci siano cortocircuiti tra 5V e GND.
4. Lavora con calma: una saldatura "fredda" (opaca, a pallina) è la causa #1 di
   malfunzionamenti.

---

## 6. Mappa pin completa (la "verità" del firmware)

Questi pin sono definiti in [`config.h`](config.h) e sono ciò che il software si
aspetta. **Wira esattamente questi numeri.** Tutti i numeri sono pin del Teensy.

### 6.1 Matrice LED
| Segnale matrice | Pin Teensy |
|-----------------|-----------|
| DIN (dati) | **17** |
| +5V | **5V** |
| GND | **GND** |

### 6.2 Scheda audio (Teensy Audio Adaptor, Rev D)
Il modo più semplice e affidabile è **impilare** la scheda audio sopra il Teensy
con i pin header: così questi collegamenti si fanno da soli. Se invece la cabli
a mano, collega:

| Segnale audio | Pin Teensy |
|---------------|-----------|
| MCLK | **23** |
| BCLK | **21** |
| LRCLK (WS) | **20** |
| TX (DIN al codec) | **7** |
| RX (DOUT dal codec) | **8** |
| SDA (I2C) | **18** |
| SCL (I2C) | **19** |
| 3,3V | **3.3V** |
| GND | **GND** |

> La SD si usa dallo **slot integrato del Teensy 4.1**, non da quello della
> scheda audio.

### 6.3 Encoder (CLK, DT, SW = pulsante)
Ogni encoder ha 3 segnali da collegare + alimentazione. Il **ruolo** di ogni
encoder è deciso dal firmware in base ai pin; la posizione fisica la scegli tu,
ma ti consiglio di disporli da sinistra a destra come in tabella.

| Encoder (ruolo nel firmware) | CLK | DT | SW (pulsante) |
|------------------------------|-----|----|----|
| **SINISTRO** — cursore su/giù, cancella, single-mode | **5** | **22** | **15** |
| **CENTRALE-SINISTRO** — pagina, disegna nota, BPM | **9** | **14** | **16** |
| **CENTRALE-DESTRO** — play/pausa, volume, filtro/seek (4° encoder) | **32** | **33** | **41** |
| **DESTRO** — cursore sin/destra, mute, velocity | **4** | **2** | **3** |

Inoltre, per ogni encoder:
- il pin **"+"** dell'encoder va a **3,3V**;
- il pin **GND** dell'encoder va a **GND**.

> Hai solo 3 encoder? Imposta `#define HAS_ENCODER4 0` in `config.h`. In quel
> caso il filtro e il seek sono disattivati e il **volume** passa
> sull'encoder sinistro.

### 6.4 OLED opzionale (fork)
Condivide lo **stesso bus I2C dell'audio** (nessun pin extra: stesso SDA/SCL).
| Segnale OLED | Pin Teensy |
|--------------|-----------|
| SDA | **18** |
| SCL | **19** |
| VCC | **3,3V** |
| GND | **GND** |

Indirizzo I2C predefinito **0x3C** (alcuni pannelli usano 0x3D).

---

## 7. Montaggio passo-passo

### Fase 1 — Preparare il Teensy 4.1
1. Salda i **due chip PSRAM** nelle piazzole sul retro del Teensy (vedi cap. 2:
   se non te la senti, prendi un Teensy con PSRAM già montata).
2. Salda gli **header** sui bordi del Teensy (e quelli per la scheda audio se la
   vuoi impilare).
3. Collega il Teensy via USB al PC e verifica che venga riconosciuto (lo
   testeremo meglio nella Fase 7).

### Fase 2 — Scheda audio
1. Impila la scheda audio sul Teensy (consigliato) **oppure** cabla i segnali
   della tabella 6.2.
2. Collega le cuffie al jack 3,5 mm (per i test).

### Fase 3 — Matrice LED 16x16
1. Individua sulla matrice la **freccia di ingresso dati** (input): si collega
   al pin **17**. L'uscita (output) resta libera.
2. Collega **5V** e **GND** della matrice ai rispettivi pin.
3. **Alimentazione**: il firmware usa colori a bassa luminosità, quindi il
   consumo è contenuto e di solito l'USB basta. Se in futuro alzi la luminosità,
   inietta i 5V alla matrice da un alimentatore dedicato e **unisci le masse
   (GND comune)** tra Teensy e matrice.

### Fase 4 — Encoder
1. Per ciascun encoder collega CLK, DT, SW secondo la tabella 6.3, più "+"
   (3,3V) e GND.
2. Tieni i fili ordinati ed etichettali: incrociare CLK/DT è l'errore più
   comune (si corregge anche via software, vedi troubleshooting).

### Fase 5 — OLED (opzionale)
1. Collega i 4 fili della tabella 6.4. Essendo sullo stesso bus dell'audio, basta
   collegarsi in parallelo a SDA/SCL.

### Fase 6 — Controllo finale prima di accendere
1. Col multimetro verifica **assenza di corto** tra 5V e GND e tra 3,3V e GND.
2. Ricontrolla che 5V/3,3V/GND siano nei pin giusti.

---

## 8. Software: caricare il firmware

### 8.1 Installazione ambiente
1. Installa **Arduino IDE**.
2. Installa **Teensyduino** (l'add-on PJRC che aggiunge il supporto Teensy).

### 8.2 Librerie richieste
Installa queste librerie (Library Manager o da GitHub):
- WS2812Serial
- FastLED (≥ 3.9.x)
- Encoder (Paul Stoffregen) — inclusa in Teensyduino
- Audio (Teensy Audio Library) — inclusa in Teensyduino
- Mapf
- TeensyPolyphony (newdigate)
- teensy-variable-playback (newdigate)
- avdweb_Switch
- **Solo se usi l'OLED del fork:** Adafruit_SSD1306 e Adafruit_GFX

### 8.3 Passo OBBLIGATORIO: ResamplingReader.h
Dentro la libreria `teensy-variable-playback` di newdigate, **sostituisci** il
file `ResamplingReader.h` con quello fornito qui:
[`_DOCS/ResamplingReader.h`](_DOCS/ResamplingReader.h). Aiuta a evitare errori di
puntatore nullo (nullptr).

### 8.4 Impostazioni di compilazione
Nel menu **Tools** di Arduino IDE:
- **Board:** Teensy 4.1
- **USB Type:** **Serial + MIDI** (necessario: il MIDI passa dalla porta USB)
- CPU Speed: predefinita (600 MHz)

### 8.5 (Fork) Attivare OLED e MIDI clock out
Apri [`config.h`](config.h) e, se vuoi, metti a `1`:
```c
#define OLED_ENABLED 1            // attiva lo schermo OLED
#define MIDI_CLOCK_OUT_ENABLED 1  // invia il clock MIDI a strumenti esterni
```
Lasciandoli a `0` (default) il NI404 si comporta come l'originale.

### 8.6 Compilare e caricare
1. Apri `soundpauli_ni404.ino`.
2. Premi **Upload** (il Teensy entra in programmazione da solo; in caso premi il
   pulsantino sul Teensy).

---

## 9. Preparare la micro SD (campioni)

Il firmware cerca i campioni sulla SD con questa **struttura precisa**:

```
/samples/<cartella>/_<numero>.wav
```

dove `<numero> = cartella*100 + indice`. Esempi reali (vedi cartella `_SDCARD/`
di questo progetto):

```
/samples/0/_1.wav      (cartella 0, campione 1)
/samples/0/_2.wav
/samples/0/_99.wav
/samples/1/_100.wav    (cartella 1, campione 0)
/samples/1/_101.wav
/samples/2/_200.wav    (cartella 2, campione 0)
```

Regole:
- Crea sulla **radice** della SD una cartella `samples`, e dentro le cartelle
  numerate `0`, `1`, `2`, ... (fino a 9).
- I file devono chiamarsi `_<numero>.wav` con la numerazione qui sopra.
- **Formato audio richiesto: WAV mono, 16 bit, 44100 Hz.**

### Convertire i tuoi campioni
Nella cartella `_SDCARD/` trovi `wavmaker.py`: converte automaticamente qualsiasi
WAV nel formato giusto (mono, 16 bit, 44,1 kHz) e li rinomina `_N.wav`.
1. Metti i tuoi `.wav` in una cartella insieme a `wavmaker.py`.
2. Esegui `python wavmaker.py`.
3. Inserisci il **numero di partenza** richiesto (es. `1` per la cartella 0,
   `100` per la cartella 1, ...).
4. Sposta i file `_N.wav` ottenuti nella relativa cartella `samples/<n>/`.

> "Sample pack" (cap. del manuale d'uso): sono cartelle numerate `1`..`99` sulla
> radice della SD, ognuna con dentro `1.wav`..`12.wav`. Le crea/usa direttamente
> il NI404 dal menu, non devi prepararle a mano.

---

## 10. Primo avvio e test

1. Inserisci la SD, collega le cuffie, alimenta via USB.
2. All'accensione vedrai una **animazione/logo** sulla matrice.
3. Se manca la SD compare l'icona **"noSD"** (rossa): spegni, inserisci la SD,
   riaccendi.
4. Muovi l'encoder **sinistro** e **destro**: deve muoversi un puntino bianco
   pulsante (il cursore).
5. Premi (push) l'encoder **centrale-sinistro** per piazzare una nota: dovresti
   sentire il campione.
6. Click sull'encoder **centrale-destro**: Play/Pausa.

Per imparare a suonarlo, vai al **Manuale d'Uso** ([`MANUALE_USO.md`](MANUALE_USO.md)).

---

## 11. Risoluzione problemi

| Sintomo | Probabile causa / rimedio |
|--------|----------------------------|
| Non si accende / non riconosciuto dal PC | Cavo USB solo-carica (usane uno dati); saldature header; corto 5V-GND |
| Si riavvia da solo / crash dopo pochi secondi | PSRAM mancante o mal saldata; alimentazione USB debole (usa 5V ≥ 2A) |
| LED non si accendono / colori sbagliati | DIN non sul pin 17; freccia dati invertita (usa l'ingresso); GND non comune |
| Solo alcuni LED accesi a caso | Alimentazione insufficiente alla matrice; GND comune mancante |
| Un encoder gira "al contrario" (su/giù invertiti) | Inverti i fili **CLK e DT** di quell'encoder |
| Un encoder non fa nulla | Pulsante/segnali sui pin sbagliati; ricontrolla tabella 6.3 |
| Nessun suono in cuffia | Scheda audio non collegata bene (pin 7,8,20,21,23,18,19); `USB Type` non impostato; volume a 0 |
| Compilazione: errori nullptr / ResamplingReader | Non hai sostituito `ResamplingReader.h` (vedi 8.3) |
| Campioni non partono / canale muto | Struttura/percorso SD errati; WAV non mono-16bit-44.1k (usa `wavmaker.py`) |
| OLED nero | `OLED_ENABLED` non a 1; indirizzo 0x3D invece di 0x3C; SDA/SCL invertiti |

---

## 12. Schema riepilogo pin (cheat-sheet)

```
LED matrix DIN ............ 17        Audio MCLK ... 23   Audio SDA ... 18
                                      Audio BCLK ... 21   Audio SCL ... 19
Encoder SINISTRO  CLK 5  DT 22 SW 15  Audio LRCLK .. 20
Encoder C-SX      CLK 9  DT 14 SW 16  Audio TX ..... 7
Encoder C-DX      CLK 32 DT 33 SW 41  Audio RX ..... 8
Encoder DESTRO    CLK 4  DT 2  SW 3   OLED ......... SDA 18 / SCL 19 (0x3C)
```

Alimentazioni: matrice = 5V; encoder e OLED e audio = 3,3V; GND **sempre in
comune** tra tutto.

Buona costruzione! Quando suona, passa al manuale d'uso.
