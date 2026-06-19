# 🧠 Sotto il cofano: il Teensy e il codice di ichosynth

### Cappello introduttivo · ICHOS 2026 · Taranto

> Un racconto a grandi linee di **cosa** c'è dentro lo strumento e **come**
> ragiona il suo programma. Non serve saper programmare per seguirlo: è la mappa
> mentale per capire cosa stiamo costruendo.

---

## 1 · Il Teensy 4.1 — il cervello

L'ichosynth è costruito attorno a una piccola scheda chiamata **Teensy 4.1**.
È un **microcontrollore**: un computer minuscolo, grande come un pollice, che
non ha schermo né sistema operativo ma esegue *un solo programma*, all'infinito,
appena riceve corrente.

Cosa lo rende speciale:

- **Potenza fuori scala** per le sue dimensioni: un processore **ARM Cortex-M7 a
  600 MHz**. È nato per fare **audio in tempo reale** — proprio quello che ci serve.
- Lo crea **PJRC** (Paul Stoffregen) e si programma con l'ambiente **Arduino**:
  stessa semplicità di un Arduino, ma con i muscoli.
- Ha uno **slot micro SD** integrato (per i campioni) e accetta la **PSRAM**:
  16 MB di memoria extra che saldiamo sotto la scheda.
- Parla **USB-MIDI**: può sincronizzarsi con altri strumenti.

Da solo il Teensy non fa suono: lo affianchiamo a una **scheda audio (codec
SGTL5000)** che trasforma i numeri calcolati dal Teensy in un segnale analogico
per le **cuffie**. E gli diamo un "volto": una **matrice di 256 LED (16×16)** che
è allo stesso tempo schermo e tastiera, **4 manopole (encoder)**, **3 pulsanti**
(PLAY/MENU/REC) e un piccolo **display OLED** che riassume lo stato.

> In una frase: il Teensy *pensa* (calcola il suono, legge le manopole, accende i
> LED), la scheda audio *parla* (manda il suono in cuffia), la matrice *mostra e
> riceve* (display + strumento).

---

## 2 · Com'è fatto un programma per Teensy

Ogni programma Arduino/Teensy ha **due funzioni** fondamentali:

```
setup()   →  viene eseguita UNA volta, all'accensione   (la preparazione)
loop()    →  viene ripetuta all'INFINITO, per sempre     (il battito)
```

- **`setup()`** prepara tutto: accende le periferiche, carica i dati, costruisce
  il motore audio.
- **`loop()`** è il battito cardiaco: legge gli ingressi, aggiorna lo schermo,
  reagisce a quello che fai — decine di volte al secondo.

Il programma che fa girare ichosynth è il **firmware reale di TŒRN** (il groovebox
open-source di SP_/soundpauli): il file principale è **`toern.ino`** insieme agli
altri file `.ino` del progetto. Noi lo compiliamo **immutato** e gli affianchiamo
solo i nostri "driver" per l'hardware economico (encoder KY-040, pulsanti, OLED) —
vedi la sezione 8.

---

## 3 · Cosa succede all'accensione — `setup()`

All'avvio il Teensy esegue, in ordine, più o meno questo (versione semplificata
di ciò che c'è nel codice):

1. **Accende la comunicazione** e controlla se al riavvio precedente c'è stato un
   errore (*CrashReport*).
2. **Prepara i pin** degli encoder e dei pulsanti, e avvia la **matrice LED**.
3. **Mostra il logo** sulla matrice (`showIntro`).
4. **Aspetta la micro SD**: se manca, disegna l'icona "noSD" e resta in attesa
   (`drawNoSD`). *(Per questo una board "nuda" senza SD sembra riavviarsi: sta
   solo aspettando la scheda.)*
5. **Carica i campioni** dalla SD nella PSRAM (il sample pack).
6. **Costruisce il "grafo audio"** — vedi sezione 5 — collegando lettori di
   campioni, voci sintetizzate, inviluppi, filtri, effetti e mixer.
7. **Accende il codec audio** e riserva la memoria audio (`AudioMemory`).
8. *(nostra aggiunta)* inizializza l'**OLED** di stato (`ichosOledBegin()`).
9. **Prepara encoder e pulsanti**: dice al programma cosa fare a rotazione, click,
   pressione lunga…

A fine `setup()` lo strumento è pronto a suonare.

---

## 4 · Il battito — `loop()`

Da qui in poi il Teensy ripete questo ciclo, velocissimo:

```
loop():
   leggi il MIDI (clock e note in arrivo)
   interroga le 4 manopole e i 3 pulsanti  (chi è stato premuto/girato?)
   interpreta il gesto                     (sto disegnando una nota? cambiando pagina? ...)
   aggiorna la matrice LED e l'OLED        (ridisegna la griglia + lo stato)
```

Un dettaglio elegante: i gesti delle manopole (click, pressione lunga, combo di
due pulsanti) non vengono interpretati alla cieca, ma valutati con una piccola
macchina a stati che distingue, ad esempio, un click corto da una pressione tenuta.

---

## 5 · Il cuore invisibile: il motore audio

Qui sta la magia del Teensy. Il suono **non** viene generato dentro il `loop()`.
Lavora in sottofondo la **Teensy Audio Library**, che gira **sugli interrupt** —
cioè in modo indipendente, prioritario, senza che il programma principale debba
occuparsene istante per istante.

Funziona come un **sintetizzatore modulare**: tanti "moduli" collegati da "cavi".
Per ogni voce, il percorso del segnale è più o meno questo:

```
[campione in PSRAM] → [lettore/player] → [inviluppo ADSR] → [filtro] → [effetti] → [mixer] → [codec audio] → 🎧
```

- Il **player** legge il campione dalla PSRAM (e può cambiarne l'intonazione).
- L'**inviluppo** dà forma al suono nel tempo (attacco, rilascio…).
- Il **filtro** ne scurisce o sagoma il timbro *(è qui che agisce la rotazione
  degli encoder in FILTER mode)*.
- Gli **effetti** (bitcrusher, Moog ladder, reverb…) colorano la voce.
- Il **mixer** somma le voci; il **codec** le trasforma in segnale per le cuffie.

Il `loop()` non "fa" il suono: si limita a **configurare i parametri** (quale
campione, che volume, quanto filtro) e il motore audio fa il resto in tempo reale.

---

## 6 · La griglia 16×16 — schermo e sequencer

<p align="center">
  <img src="assets/grid-concept.svg" alt="La matrice 16x16: colonne = passi nel tempo, righe = voci" width="380">
</p>

La matrice di LED è insieme **display** e **spartito**:

- le **colonne** sono i passi nel tempo (la sequenza che si ripete),
- le **righe** sono le **voci** (i diversi campioni), ognuna con un colore.

Una grande tabella in memoria ricorda *cosa* suona e *dove*. Un **timer hardware**
fa avanzare il "cursore di riproduzione" al ritmo del **BPM** e, ad ogni passo, fa
partire i campioni delle note accese. Via **USB-MIDI** lo strumento può sincronizzarsi
con altri dispositivi, per suonarci insieme.

---

## 7 · La memoria: perché serve la PSRAM

I campioni audio sono **grandi**: non entrano nella poca RAM interna del Teensy.
Per questo li teniamo nella **PSRAM** (16 MB di memoria esterna saldata sotto la
scheda, indicata nel codice come `EXTMEM`). È il motivo per cui la PSRAM è
**obbligatoria**: senza, lo strumento non ha dove mettere i suoni e non parte.

---

## 8 · Cos'è ichosynth (e cosa abbiamo aggiunto)

ichosynth **è TŒRN** — il groovebox di SP_ (soundpauli) — ricostruito a mano con
componenti economici e saldabili. Il firmware è quello reale e immutato, con tutte
le sue funzioni: 8 voci campione + 3 voci sintetizzate, polifonia, effetti per voce
(reverb, bitcrusher, Moog ladder, detune, ottava), griglia 16×16, pagine,
sotto-pattern, song mode, velocity/probabilità/condizioni, mute, note-shift e
copia-incolla, sample pack e browser SD, salvataggio/caricamento, registrazione
dal vivo (MIC/LINE con count-in), USB-MIDI, tap-tempo.

Il lavoro "nostro" non è cambiare il suono, ma **rimpiazzare l'hardware costoso**
di TŒRN con parti da pochi euro, scrivendo i driver che le fanno parlare con il
firmware originale:

- **4 encoder KY-040** al posto dei costosi encoder I²C RGB di TŒRN
  (driver in `teensy/libraries/i2cEncoderLibV2`).
- **3 tact switch** (PLAY/MENU/REC) al posto dei 3 sensori capacitivi
  (driver in `teensy/libraries/FastTouch`).
- **OLED SSD1306**: un piccolo schermo che mostra canale, modo, trasporto, BPM,
  volume e pagina (driver in `teensy/libraries/IchosOled`) — al posto del
  feedback a colori degli anelli RGB.

Niente PCB: tutto a fili. La 2ª striscia LED reattiva di TŒRN è rimossa in questa
build (libera il pin 24).

---

## 9 · Mappa mentale dei file

| File / cartella | A cosa serve |
|---|---|
| `toern.ino` (+ gli altri `.ino`) | il firmware reale di TŒRN (`setup` + `loop` + tutto il resto) |
| `teensy/build_toern.py` | compila il firmware → `teensy/firmware/toern.hex` |
| `teensy/libraries/i2cEncoderLibV2` | driver dei 4 encoder KY-040 |
| `teensy/libraries/FastTouch` | driver dei 3 tact switch |
| `teensy/libraries/IchosOled` | driver dell'OLED di stato |
| `teensy/README.md` | il doc del port (mappa pin, build, OLED) |
| `_DOCS/MAPPA_CONTROLLI.md` | come encoder e pulsanti pilotano TŒRN |

---

<div align="center">

**In sintesi:** un cervello potente (Teensy) che, in un ciclo infinito, legge le
tue manopole e ridisegna una griglia di luci, mentre un motore audio invisibile
trasforma campioni in musica. Tutto il resto è dettaglio — e ora sapete dov'è.

*ichosynth · build a basso costo di TŒRN (SP_/soundpauli) · firmware open-source MIT*

</div>
