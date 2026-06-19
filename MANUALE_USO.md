**🇮🇹 Italiano** · [🇬🇧 English](USAGE_MANUAL.md)

<div align="center">

# 🎮 ichosynth — Manuale d'Uso

### Come suonare il campionatore-sequencer che si *disegna*

Disegni la musica su una griglia 16×16 con **4 manopole** e **3 pulsanti**. Niente computer, niente menù da memorizzare: giri, premi, ascolti.

[![Livello: Principiante](https://img.shields.io/badge/Livello-Principiante-2ea44f.svg)](#)
[![Build: 4 encoder + 3 pulsanti](https://img.shields.io/badge/Build-4%20encoder%20%2B%203%20pulsanti-orange.svg)](#)
[![Firmware: TŒRN di SP_](https://img.shields.io/badge/firmware-T%C5%92RN%20%C2%B7%20SP__-blueviolet.svg)](https://toern.live)
[![Vedi anche: Costruzione](https://img.shields.io/badge/Vedi%20anche-Manuale%20di%20Costruzione-blue.svg)](MANUALE_COSTRUZIONE.md)

</div>

> 🎧 **Non serve un computer per suonare**: il tuo **ichosynth** genera tutto da solo. Colleghi le
> **cuffie**, accendi via USB e via.

> ℹ️ **Questo è il vero TŒRN.** ichosynth fa girare il firmware completo **TŒRN** (di SP_/soundpauli,
> [toern.live](https://toern.live)) su un Teensy 4.1, costruito con componenti economici saldati a mano:
> **4 encoder KY-040**, **3 tact switch** e un **OLED SSD1306**. Dove il TŒRN originale ti diceva lo
> stato col colore acceso degli anelli degli encoder, la nostra build lo mostra in chiaro sull'**OLED**.

---

## 📑 Indice

- [1 · Concetto in 30 secondi](#1--concetto-in-30-secondi)
- [2 · L'hardware: 4 manopole + 3 pulsanti](#2--lhardware-4-manopole--3-pulsanti)
- [3 · Leggere la griglia e l'OLED](#3--leggere-la-griglia-e-loled)
- [4 · I 3 pulsanti (B1 B2 B3)](#4--i-3-pulsanti-b1-b2-b3)
- [5 · Modalità DRAW (disegno)](#5--modalità-draw-disegno)
- [6 · Pagine, pattern e subpattern](#6--pagine-pattern-e-subpattern)
- [7 · Mute (silenziare le voci)](#7--mute-silenziare-le-voci)
- [8 · Volume e BPM](#8--volume-e-bpm)
- [9 · Velocity, probabilità e condizioni](#9--velocity-probabilità-e-condizioni)
- [10 · Modalità SINGLE (una sola voce)](#10--modalità-single-una-sola-voce)
- [11 · Modalità FILTER e DSP per-voce](#11--modalità-filter-e-dsp-per-voce)
- [12 · Cambiare campione (Sample Browser)](#12--cambiare-campione-sample-browser)
- [13 · Colori delle voci e le voci synth](#13--colori-delle-voci-e-le-voci-synth)
- [14 · Sample pack](#14--sample-pack)
- [15 · Salvare e caricare (Menu)](#15--salvare-e-caricare-menu)
- [16 · Registrazione dal vivo (REC)](#16--registrazione-dal-vivo-rec)
- [17 · Modalità SONG](#17--modalità-song)
- [18 · MIDI e tap-tempo](#18--midi-e-tap-tempo)
- [19 · Mappa modalità & comandi](#19--mappa-modalità--comandi)
- [20 · Problemi comuni](#20--problemi-comuni)

---

## 1 · Concetto in 30 secondi

La **griglia 16×16** è il tuo foglio musicale. Una "testina" di riproduzione scorre da sinistra a
destra: ogni colonna che tocca, suona le note che ci hai messo.

<p align="center">
  <img src="assets/grid-concept.svg" alt="La griglia 16x16: righe = voci colorate, colonne = step, testina di Play" width="560">
</p>

- Le **colonne** (sinistra→destra) sono i **16 step** di una battuta (una pagina si può concatenare a **32×16**).
- Ogni **riga** è una **voce** (un campione o un synth), identificata da un **colore**.
- Più pagine in fila formano un **pattern**; più pattern formano una **song**.

> 💡 Flusso base: **disegni note → premi PLAY (B1) → loop**. Cambi campioni, BPM e volume al volo, senza fermarti.

---

## 2 · L'hardware: 4 manopole + 3 pulsanti

In alto ci sono **4 encoder** — **E1 E2 E3 E4**, da sinistra a destra. Sotto stanno **3 tact switch** —
**B1 B2 B3**. Ogni encoder si **gira** e si **preme** (click).

```
   [ E1 ]   [ E2 ]   [ E3 ]   [ E4 ]     ← 4 manopole (gira + premi)
   [  B1  ] [  B2  ] [  B3  ]            ← 3 pulsanti
```

<p align="center">
  <img src="assets/encoders.svg" alt="Gli encoder e i pulsanti di ichosynth con i gesti" width="720">
</p>

I gesti che il firmware riconosce:

| Gesto | Cosa significa |
|---|---|
| **Gira** (E1–E4) | cambia il valore / muove il cursore nel contesto attuale |
| **Click corto** (premi un encoder) | conferma / agisci (il senso dipende dalla modalità) |
| **Pressione lunga** (tieni un encoder) | una seconda azione (es. E1 tenuto = mute/subpattern) |
| **Tap di un pulsante** (B1/B2/B3) | la funzione principale del pulsante |
| **Tieni un pulsante** | la funzione "tenuta" del pulsante (es. B3 tenuto = count-in registrazione) |
| **Combo B1+B2** | una scorciatoia — **conta l'ordine** con cui li premi (vedi cap. 11 e 12) |

> 💡 **Niente doppio click**: gli encoder KY-040 non ne hanno bisogno. Ogni azione è una rotazione, un
> click, una pressione lunga, un tap di pulsante o una combo a due pulsanti.

Cosa fa ogni encoder cambia con la modalità. Ecco il quadro generale (i dettagli nei capitoli relativi):

| Modo | E1 gira | E2 gira | E3 gira | E4 gira |
|---|---|---|---|---|
| **DRAW** | Y / nota (riga) | pagina | filtro rapido del canale | X / colonna |
| **SINGLE** | canale | nota (pitch) | — | X / colonna |
| **FILTER** | slider 1 | slider 2 | slider 3 | slider 4 |
| **MENU** | — | valore | valore | naviga le pagine menu |
| **VELOCITY** | velocity | probabilità | volume canale | condizione / timing |
| **SONG** | — | pattern | — | posizione (1–64) |

I **click** degli encoder più utili (in DRAW/SINGLE):

- **E3 click** = **Play / Pausa**.
- **E1 pressione lunga** = entra in mute / subpattern (rilascia per ripristinare).
- **E1 click @ riga 16** (in SINGLE) = NOTE SHIFT.
- **E4 click** = conferma / entra in un sotto-menu.
- **E1 click** (in MENU) = indietro / esci.

---

## 3 · Leggere la griglia e l'OLED

- **Righe** = le voci (8 voci campione + 3 voci synth), ognuna col suo **colore** (vedi [cap. 13](#13--colori-delle-voci-e-le-voci-synth)).
- **Colonne** = i 16 step della pagina corrente.
- **Riga in alto (status)**: indicatori delle pagine e spie di stato (copia attiva, ecc.). Durante il Play gli indicatori pagina diventano **verdi**.
- **Testina di Play**: la colonna evidenziata che avanza mentre suoni (il ▼ nell'immagine sopra).

> 📟 Il TŒRN originale mostrava lo stato dal vivo col **colore degli anelli degli encoder**. La nostra
> build non ha gli anelli RGB, quindi l'**OLED** mostra le stesse informazioni in chiaro: **canale
> corrente, modalità, stato trasporto (PLAY / REC / STOP), BPM, volume e pagina**. Dagli un'occhiata in
> qualsiasi momento per sapere esattamente dove sei.

---

## 4 · I 3 pulsanti (B1 B2 B3)

I tre tact switch sono il cuore del trasporto e della navigazione:

| Pulsante | Funzione principale | Fa anche… |
|---|---|---|
| **B1 · PLAY** | avvia il play; attiva/disattiva **SINGLE**; esce dalle altre modalità tornando a **DRAW** | **tenuto all'accensione** = svuota la RAM (ripartenza pulita) |
| **B2 · MENU** | entra / esci dal **Menu** e dai sotto-modi | esce da un sotto-modo tornando a DRAW/SINGLE |
| **B3 · REC** | **registra** (tap o tieni) | **PAUSA** durante il play · **tap-tempo BPM** · tieni **>300 ms** = **count-in** di registrazione |

> 💡 **PLAY è B1** (un tap singolo), non un gesto di encoder. **PAUSA è B3** mentre una song sta suonando.

---

## 5 · Modalità DRAW (disegno)

È la schermata principale, quella di default, dove crei i pattern.

| Azione | Gesto |
|---|---|
| 🧭 **Muovere il cursore** | gira **E1** (su/giù, riga/nota) e **E4** (sin/destra, colonna) |
| 📄 **Cambiare pagina** | gira **E2** |
| ✏️ **Aggiungere / cambiare una nota** | premi sul punto del cursore (senti subito il suono); ripremendo su una nota, la voce cicla |
| ▶️ **Play / Pausa** | **E3 click** (la pausa durante il play è anche **B3**) |
| 🎚️ **Filtro rapido del canale** | gira **E3** per addolcire/illuminare al volo la voce sotto il cursore |
| 🔇 **Mute / subpattern** | **tieni E1** (rilascia per ripristinare) |

> 💡 In DRAW E3 è la manopola del "trasporto": **premila** per Play/Pausa, **giralo** per ritoccare il
> filtro del canale corrente senza lasciare la griglia.

---

## 6 · Pagine, pattern e subpattern

- La griglia mostra **una pagina** (16 step) per volta; gira **E2** per spostarti tra le pagine.
- Le pagine con note vengono suonate in sequenza in loop e formano un **pattern**. I pattern si
  concatenano in [modalità SONG](#17--modalità-song).
- **Subpattern**: **tieni E1** per cadere in una variazione momentanea del pattern corrente, poi rilascia
  per tornare indietro di scatto — ideale per stacchi e fill dal vivo.
- **Copia/incolla note e note-shift** ti fanno spostare e duplicare gli step; lo stato attivo di
  copia/note-shift appare sulla riga in alto della griglia (e sull'OLED).

---

## 7 · Mute (silenziare le voci)

- Porta il cursore su una voce e **tieni E1** per mutarla / cadere nel suo subpattern; rilascia per ripristinare.
- I canali mutati sono indicati **sulla griglia stessa**, così vedi sempre a colpo d'occhio cosa è in silenzio.

---

## 8 · Volume e BPM

- **Volume** e **BPM** sono sempre leggibili sull'**OLED**.
- **Tap-tempo**: tocca **B3 (REC)** a tempo per impostare il **BPM** a orecchio.
- Il **volume per-canale** si regola in [modalità VELOCITY](#9--velocity-probabilità-e-condizioni) con **E3**.

---

## 9 · Velocity, probabilità e condizioni

TŒRN dà a ogni step più di un semplice on/off. In **VELOCITY** le quattro manopole diventano controlli per-step:

| Manopola | Controlla |
|---|---|
| **E1** | **velocity** (quanto è forte lo step) |
| **E2** | **probabilità** (chance che lo step suoni) |
| **E3** | **volume del canale** |
| **E4** | **condizione / timing** (es. suona ogni N passaggi, micro-timing) |

Usa **B2 (MENU)** per scorrere i sotto-modi; **B1 (PLAY)** ti riporta a DRAW.

---

## 10 · Modalità SINGLE (una sola voce)

Utile per lavorare in dettaglio su un campione (es. una melodia su più altezze).

- **Entra / esci da SINGLE**: tocca **B1 (PLAY)** per attivare/disattivare SINGLE sulla voce a fuoco.
- In SINGLE: **E1 gira** = scegli il **canale**, **E2 gira** = la **nota (pitch)**, **E4 gira** = la **colonna (X)**.
- Valgono gli stessi gesti di disegno/cancellazione di DRAW, ma agisci solo sulla voce selezionata.

### Note Shift (in SINGLE)
- Porta il cursore sulla riga 16 e **clicca E1** per entrare in **NOTE SHIFT**, poi muovi le note con le manopole.

---

## 11 · Modalità FILTER e DSP per-voce

ichosynth ha tutto il DSP per-voce di TŒRN: un **filtro passa-basso**, **reverb**, **bitcrusher**,
**detune**, **octave** e un **Moog ladder** sulle voci synth.

- **Entra in FILTER mode**: premi **B2 + B1 insieme, con B2 per primo** (B2-first = FILTER MODE).
  Funziona sui canali che hanno filtri (1–8, 11, 13–14).
- In FILTER mode le quattro manopole diventano **quattro slider** (**E1 E2 E3 E4**) per il DSP della voce
  selezionata. L'OLED mostra il filtro selezionato e il suo valore.
- Esci con **B2 (MENU)** o **B1 (PLAY)** per tornare a DRAW.

> 💡 Per un ritocco rapido senza modalità puoi anche solo **girare E3 in DRAW** per filtrare il canale
> sotto il cursore. La FILTER mode serve a regolare l'intero set di effetti per voce.

---

## 12 · Cambiare campione (Sample Browser)

Per assegnare un WAV diverso a una delle 8 voci campione:

1. **Apri il Sample Browser**: premi **B1 + B2 insieme, con B1 per primo** (o entrambi insieme). Si entra
   in SET_WAV per i canali 1–8.
2. **Naviga** con le manopole: cambia **cartella** e **campione** (sfogli la SD); puoi vedere l'anteprima
   di **lunghezza** e **forma d'onda** e impostare **seek / lunghezza / reverse**.
3. **Conferma** con **E4 click** per caricare il campione selezionato sulla voce.
4. **Esci** con **B2 (MENU)**.

> 📁 I campioni stanno sulla microSD come `/samples/<cartella>/_<numero>.wav`
> (vedi [manuale di costruzione](MANUALE_COSTRUZIONE.md#9--preparare-la-micro-sd-campioni)). I WAV devono
> essere mono, 16-bit, 44,1 kHz — `wavmaker.py` li prepara per te.

> ⏱️ **Nella combo conta l'ordine**: **B2 prima** → FILTER MODE; **B1 prima (o simultanei)** → SAMPLE
> BROWSER. C'è un breve cooldown di 350 ms tra una combo e l'altra.

---

## 13 · Colori delle voci e le voci synth

Ogni voce ha un colore fisso (definito in [`colors.h`](colors.h)):

<p align="center">
  <img src="assets/voice-colors.svg" alt="Legenda colori voci: 1 rosso, 2 blu, 3 giallo, 4 verde, 5 magenta, 6 lime, 7 arancione, 8 turchese, voci synth" width="540">
</p>

Ci sono **8 voci campione** più **3 voci synth**. Le voci synth suonano onde generate internamente e
seguono le altezze di una scala; hanno il loro **filtro Moog ladder** (si regola in [FILTER mode](#11--modalità-filter-e-dsp-per-voce)).
TŒRN è **polifonico**, quindi più voci suonano insieme.

---

## 14 · Sample pack

Un "sample pack" è un set completo di voci salvato sulla SD: richiami al volo un intero kit.

- Apri il Sample Browser ([cap. 12](#12--cambiare-campione-sample-browser)) e usa i comandi del pack per
  **caricare** un pack numerato sulle 8 voci campione.
- I pack ti fanno scambiare un intero kit tra le song senza ricostruirlo voce per voce.

> 📁 Sulla SD un pack è una cartella numerata con dentro i suoi file `.wav`; li gestisce ichosynth, non
> serve crearli a mano.

---

## 15 · Salvare e caricare (Menu)

- **Entra nel Menu**: tocca **B2 (MENU)**.
- Naviga le pagine del menu con **E4** (gira), regola i valori con **E2 / E3**, e **conferma / entra in
  un sotto-menu con E4 click**; **E1 click = indietro**.
- Dal Menu **salvi** e **carichi** le song da/verso la microSD.
- **Esci** dal Menu con **B2 (MENU)** di nuovo, oppure **B1 (PLAY)** per tornare subito a DRAW.

---

## 16 · Registrazione dal vivo (REC)

ichosynth registra l'audio direttamente dal suo ingresso nel canale corrente.

1. Scegli il **canale** in cui registrare.
2. **Tieni B3 (REC)** per registrare dall'ingresso (**MIC** o **LINE**; la scelta appare sull'OLED).
3. **Tieni B3 > 300 ms** per avere prima un **count-in** (4 beat al BPM corrente), poi la registrazione parte sul tempo.
4. Rilascia **B3** per fermare; la presa viene salvata sulla SD e caricata sul canale, così sopravvive al riavvio.

> 💡 **B3 è multiuso**: un tap rapido è **tap-tempo** / **PAUSA durante il play**; una tenuta è
> **registrazione**. L'indicatore di trasporto sull'OLED mostra **REC** mentre registri.

---

## 17 · Modalità SONG

La modalità SONG concatena i tuoi pattern in un arrangiamento completo.

- In SONG: **E2 gira** = scegli il **pattern**, **E4 gira** = la **posizione** nella song (1–64).
- Costruisci la sequenza di pattern, poi **PLAY (B1)** fa suonare tutta la song.
- Gli stati di mute e la posizione nella song appaiono **sulla griglia**, così segui l'arrangiamento dal vivo.

---

## 18 · MIDI e tap-tempo

- **USB MIDI**: ichosynth è un dispositivo **USB MIDI**. Collegato via USB suona/riceve MIDI con un
  computer o altra strumentazione.
- **Tap-tempo**: tocca **B3 (REC)** a tempo per impostare il BPM a sensazione — senza menù.

---

## 19 · Mappa modalità & comandi

Da DRAW (la schermata principale) raggiungi tutto con manopole, pulsanti e le due combo:

<p align="center">
  <img src="assets/modes-map.svg" alt="Mappa delle modalità e dei gesti per raggiungerle" width="720">
</p>

Legenda: **E1–E4** = le quattro manopole (gira o clicca) · **B1/B2/B3** = i tre pulsanti · "click" =
pressione breve · "hold" = pressione lunga · "combo" = due pulsanti insieme (l'ordine conta).

| Vuoi… | Gesto |
|-------|-------|
| Muovere cursore su/giù (riga/nota) | gira **E1** |
| Muovere cursore sin/destra (colonna) | gira **E4** |
| Cambiare pagina | gira **E2** |
| Aggiungere / cambiare una nota | premi sul punto del cursore |
| **Play / Pausa** | **E3 click** (pausa anche **B3**) |
| Filtro rapido del canale corrente | gira **E3** (in DRAW) |
| Mute / subpattern (voce corrente) | **tieni E1** |
| **PLAY** (trasporto) | **B1** |
| **MENU** (salva/carica, impostazioni) | **B2** |
| **REC** / pausa / tap-tempo | **B3** |
| Svuotare la RAM (ripartenza pulita) | **tieni B1 all'accensione** |
| Entrare/uscire da **SINGLE** | **B1** (toggle) |
| **Note Shift** (in Single) | **E1 click @ riga 16** |
| **VELOCITY** (velocity/prob/vol/condizione) | **B2** per raggiungerla → **E1/E2/E3/E4** |
| **FILTER mode** (DSP per-voce) | **B2 + B1, B2 prima** → slider su **E1–E4** |
| **Sample Browser** (set WAV) | **B1 + B2, B1 prima / insieme** → conferma **E4 click** |
| **Menu** conferma / entra sotto-menu | **E4 click** · indietro = **E1 click** |
| **Count-in** registrazione | **tieni B3 > 300 ms** |

> ⚠️ **Le due combo differiscono solo per l'ordine**: **B2 prima** → FILTER mode; **B1 prima (o insieme)**
> → Sample Browser. Aspetta ~350 ms tra una combo e l'altra.

---

## 20 · Problemi comuni

| Sintomo | Rimedio |
|---|---|
| 🔇 **Non sento nulla** | controlla volume/volume canale (OLED), che la voce non sia in mute (**tieni E1**), e che il campione esista sulla SD nel formato giusto |
| ▶️ **Non parte** | Play è **B1** (o **E3 click**); la pausa durante il play è **B3** |
| ↩️ **Una manopola va al contrario** | è un'inversione CLK/DT in fase di cablaggio (vedi manuale di costruzione) |
| 🚫 **I campioni non partono** | percorso/struttura SD errati, o WAV non mono/16-bit/44,1 kHz → usa `wavmaker.py` |
| 🤔 **Una combo ha aperto la modalità sbagliata** | attenzione all'ordine: **B2 prima** = FILTER, **B1 prima** = Sample Browser; aspetta ~350 ms e riprova |
| 💾 **Voglio ripartire da zero** | **tieni B1 all'accensione** per svuotare la RAM; salva le song sulla SD dal Menu (B2) |
| ⏱️ **Lunghezza campione** | sono supportati campioni lunghi con loop continuo |

---

<div align="center">

Buon divertimento! 🎶

*ichosynth fa girare **TŒRN** di SP_ (soundpauli) · [toern.live](https://toern.live) · su un Teensy 4.1
con 4 encoder KY-040, 3 tact switch e un OLED SSD1306.*

</div>
