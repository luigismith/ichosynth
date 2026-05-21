# NI404 — Manuale d'Uso

Come suonare il NI404: un campionatore-sequencer ispirato all'Etch-A-Sketch. Si
"disegna" la musica su una griglia di LED 16x16 usando 3–4 manopole.

> Non serve un computer per suonare: il NI404 genera tutto da solo. Colleghi le
> cuffie, accendi via USB e via.

---

## 1. Concetto in 30 secondi

- La **griglia 16x16** è il tuo foglio musicale.
- Le **colonne** (sinistra→destra) sono i **16 passi (step)** di una battuta.
- Una "testina" di riproduzione scorre da sinistra a destra: ogni colonna che
  tocca, suona le note che ci hai messo.
- Ogni **nota** ha un colore = una **voce** (un campione o un synth).
- Più pagine messe in fila formano un **pattern/song**.

Disegni note → premi Play → loop. Cambi campioni, BPM, volume al volo.

---

## 2. Le 4 manopole (encoder)

Ogni manopola si **gira** e si **preme** (click). Riconosce gesti diversi:
click singolo, doppio click, pressione lunga (hold), e "tieni premuto" (push).

| Manopola | Girando | Premendo (funzioni principali) |
|----------|---------|--------------------------------|
| **SINISTRA** | muove il cursore **su/giù** (Y) | click = cancella nota; doppio click = entra/esci da modalità Singola |
| **DESTRA** | muove il cursore **sin/destra** (X) | click = muto voce corrente; hold = muto tutto (finché tieni); doppio click = velocity |
| **CENTRALE-SX** | seleziona la **pagina** | push = disegna una nota; hold = modalità disegno continuo; (in Volume/BPM regola il BPM) |
| **CENTRALE-DX** | filtro / seek (4° encoder) | click = **Play/Pausa**; hold = schermata **Volume/BPM**; (in Volume/BPM regola il Volume) |

> Versione a 3 encoder: niente centrale-destra; il volume si regola con la
> manopola sinistra.

Il **cursore** è il puntino bianco che pulsa: indica dove stai per agire.

---

## 3. Lettura della griglia

- **Righe**: le voci. Ad ogni riga corrisponde una voce/campione, identificata da
  un **colore** (vedi cap. 11). Si possono mixare fino a 8 voci campione + voci
  synth.
- **Colonne**: i 16 step della pagina corrente.
- **Riga in alto (status)**: a sinistra le **8 pagine** (indicatori), a destra le
  spie di stato (copia attiva, ecc.). Durante il Play, gli indicatori pagina
  diventano verdi.
- **Testina di Play**: una colonna che avanza mentre suoni.

(Se hai montato l'**OLED** del fork, lì leggi in chiaro: modalità, BPM, volume,
velocity, pagina e stato Play/Stop.)

---

## 4. Modalità DRAW (disegno) — quella di default

È la schermata principale, dove crei i pattern.

### Muovere il cursore
- Manopola **sinistra** = su/giù.
- Manopola **destra** = sinistra/destra.

### Aggiungere una nota
- **Push** (tieni premuta) la manopola **centrale-sinistra** sul punto del
  cursore. Senti subito il suono.
- Se ripremi su una nota esistente, la voce **cambia** (cicla tra le voci).

### Disegnare in continuo (effetto Etch-A-Sketch)
- **Hold** (pressione lunga) sulla **centrale-sinistra** per attivare il
  *paint mode*: ora muovendo le manopole **disegni una scia di note**.
- Per smettere, rilascia/clicca una manopola (il disegno continuo si disattiva).

### Cancellare
- **Click** sulla manopola **sinistra** = cancella la nota sotto il cursore.
- **Hold** sulla manopola **sinistra** = modalità cancellazione continua: muovi
  le manopole per cancellare lungo il percorso.

### Play / Pausa
- **Click** sulla manopola **centrale-destra**.

---

## 5. Pagine e pattern

- La griglia mostra **una pagina** (16 step) per volta.
- Gira la manopola **centrale-sinistra** per cambiare pagina.
- Ci sono fino a **8 pagine** → 128 step totali per song.
- In Play, le pagine con note vengono suonate in sequenza in loop.

### Copia / incolla una pagina (in DRAW)
- **Click sinistra + click destra** insieme: copia la pagina corrente; ripeti il
  gesto su un'altra pagina per incollare.

### Cancellare l'intera pagina
- **Hold sinistra + hold centrale-sinistra** insieme.

---

## 6. Mute (silenziare le voci)

- **Click destra**: muta/smuta la **voce corrente** (quella della riga su cui sei).
- **Hold destra**: muta **tutto** finché tieni premuto (rilascia per riattivare).
  Utile per stacchi/break dal vivo.

---

## 7. Volume e BPM

- **Hold** la manopola **centrale-destra**: apre la schermata **Volume/BPM**.
- Dentro questa schermata:
  - **BPM**: manopola **centrale-sinistra** (range ~40–240).
  - **Volume**: manopola **centrale-destra** (o sinistra nella versione a 3
    encoder).
- Per uscire: **rilascia** la manopola centrale-destra (torni a DRAW).

---

## 8. Velocity (dinamica della nota)

- **Doppio click** sulla manopola **destra**: apre la modalità velocity per la
  nota sotto il cursore.
- Regola con la manopola **centrale-sinistra**.
- Esci con il **rilascio** (torni a DRAW/Single).

---

## 9. Modalità SINGLE (una sola voce alla volta)

Utile per lavorare in dettaglio su un singolo campione (es. melodie su più
altezze).

- **Entra**: **doppio click** manopola **sinistra** sulla riga della voce che
  vuoi isolare.
- **Esci**: **doppio click** manopola **sinistra** di nuovo.

In SINGLE valgono gli stessi gesti di disegno/cancellazione di DRAW, ma agisci
solo sulla voce selezionata.

### Spostare le note (Note Shift, in SINGLE)
- **Hold destra + hold centrale-destra**: entra in Note Shift.
- Muovi le note con le manopole.
- **Click centrale-sinistra** = conferma; **click sinistra** = annulla.

---

## 10. Cambiare campione (Sample Browser)

Per assegnare un file WAV diverso a una voce:

1. Entra in **SINGLE** sulla voce desiderata (cap. 9).
2. **Hold sinistra + hold destra**: apre il **browser dei campioni** (SET_WAV).
3. Naviga:
   - manopola per cambiare **cartella** e **campione** (sfoglia i file della SD);
   - vedi l'anteprima della forma d'onda / lunghezza.
4. **Click sinistra** = carica il campione selezionato sulla voce.
5. **Click centrale-sinistra** = esci.

I campioni vengono letti dalla SD nella struttura
`/samples/<cartella>/_<numero>.wav` (vedi manuale di costruzione, cap. 9).

---

## 11. Colori delle voci

Riferimento rapido (definito in [`colors.h`](colors.h)):

| Voce | Colore indicativo |
|------|-------------------|
| 1 | rosso |
| 2 | blu |
| 3 | giallo |
| 4 | verde |
| 5 | magenta |
| 6 | verde-lime |
| 7 | arancione |
| 8 | turchese |
| 13 | viola (synth) |
| 14 | bianco (synth) |

Le due voci **synth** (13 e 14) suonano onde generate internamente (sawtooth e
square) e seguono le altezze di una scala (Do3…Re5).

---

## 12. Sample Pack (set di campioni)

Un "sample pack" è un set completo di voci salvato sulla SD, così puoi
richiamare al volo un intero kit.

- In DRAW: **hold sinistra + hold destra** apre la schermata **Sample Pack**.
- Seleziona il numero del pack con la manopola.
- **Click destra** = salva il set corrente in quel pack.
- **Click sinistra** = carica il pack.
- **Click centrale-sinistra** = esci.

Sulla SD un pack è la cartella numerata `1`..`99` con dentro `1.wav`..`12.wav`
(li gestisce il NI404, non serve crearli a mano).

---

## 13. Salvare e caricare le tue song (Menu)

- In DRAW: **hold centrale-destra + hold centrale-sinistra** apre il **Menu**.
- Nel menu:
  - **Click destra** = **salva** la song nello slot corrente;
  - **Click sinistra** = **carica** la song;
  - **Click centrale-sinistra** = esci.
- Le song si salvano sulla radice della SD come file `<numero>.txt` (fino a 100).
- **Autosave/Autoload**: il NI404 salva automaticamente in `autosaved.txt` (es.
  quando metti in pausa) e ricarica quel contenuto all'accensione, così ritrovi
  il lavoro dove l'avevi lasciato.

---

## 14. MIDI

Tutto il MIDI passa dalla **porta USB** del Teensy (serve `USB Type = Serial +
MIDI` in fase di compilazione).

- **MIDI In (USB)**: il NI404 riceve note (le mappa sulla griglia/voce
  corrente), e si **sincronizza** a clock/start/stop MIDI esterni (modalità
  slave).
- **MIDI Clock Out (USB)** — *funzione di questo fork, se `MIDI_CLOCK_OUT_ENABLED
  = 1`*: quando suoni, il NI404 invia **Clock (24 PPQN), Start e Stop** così
  strumenti esterni si sincronizzano al NI404 (modalità master).
  - Se il NI404 sta già ricevendo un clock esterno, **non** genera il proprio
    (lascia comandare il master esterno).

> Le prese DIN MIDI a 5 pin (pin 0/1) sono previste sul cablaggio ma il firmware
> attuale **non** le usa: il MIDI funziona solo via USB.

---

## 15. Tabella riassuntiva comandi

Legenda: SX = sinistra, DX = destra, C-SX = centrale-sinistra, C-DX =
centrale-destra. "click" = pressione breve, "hold" = pressione lunga, "push" =
tieni premuto.

| Vuoi… | Gesto |
|-------|-------|
| Muovere cursore su/giù | gira **SX** |
| Muovere cursore sin/destra | gira **DX** |
| Aggiungere una nota | **push C-SX** |
| Disegno continuo (Etch-A-Sketch) | **hold C-SX**, poi muovi |
| Cancellare una nota | **click SX** |
| Cancellazione continua | **hold SX**, poi muovi |
| Play / Pausa | **click C-DX** |
| Mute voce corrente | **click DX** |
| Mute tutto (momentaneo) | **hold DX** |
| Cambiare pagina | gira **C-SX** |
| Copia/incolla pagina | **click SX + click DX** |
| Cancellare la pagina | **hold SX + hold C-SX** |
| Volume / BPM | **hold C-DX** (BPM=C-SX, Vol=C-DX) |
| Velocity nota | **doppio click DX** |
| Entrare/uscire modalità Single | **doppio click SX** |
| Note Shift (in Single) | **hold DX + hold C-DX** |
| Sample browser (in Single) | **hold SX + hold DX** |
| Sample Pack (in Draw) | **hold SX + hold DX** |
| Menu salva/carica (in Draw) | **hold C-DX + hold C-SX** |

---

## 16. Consigli e risoluzione problemi

- **Non sento nulla**: controlla volume (hold C-DX), che la voce non sia in mute
  (click DX), e che il campione esista sulla SD nel formato giusto.
- **Una manopola va al contrario**: è un'inversione CLK/DT in fase di
  cablaggio (vedi manuale di costruzione).
- **I campioni non partono**: percorso/struttura SD errati, o WAV non in
  mono/16-bit/44,1 kHz → usa `wavmaker.py`.
- **Ho perso il lavoro**: c'è l'autosave (`autosaved.txt`), ma salva spesso
  anche manualmente in uno slot dal Menu.
- **Lunghezza massima campione**: ~30 secondi, con loop continuo.

---

Buon divertimento! Questo firmware è dichiarato dall'autore "lontano dal
completamento": alcune funzioni (filtri, alcune scorciatoie) sono parziali. È
open-source MIT: puoi modificarlo e migliorarlo a piacere.
