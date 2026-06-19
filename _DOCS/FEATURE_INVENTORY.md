# ichosynth (port di TŒRN) — inventario completo delle feature

> Mappa di tutto ciò che il firmware fa, per decidere cosa **alleggerire**. Ricavato
> dal sorgente reale (`emulator/toern-src/`, 23.442 righe). Per ogni blocco: a cosa
> serve, quanto pesa, e se/quanto è rimovibile. Budget attuale dopo il port: FLASH
> ~342 KB (7,7 MB liberi), RAM1 ~700 byte liberi (stretta), RAM2 459 KB liberi,
> **PSRAM 16,5 MB** (servono entrambi i chip saldati), audio block ~128.

## 1. Voci e motore audio

| # | Feature | A cosa serve | Peso | Alleggerибile? |
|---|---|---|---|---|
| 1 | **8 voci campione** (canali 1-8) | sampler polifonico (`AudioPlayArrayResmp`, TeensyVariablePlayback) da PSRAM | grosso: PSRAM + audio block | ridurre il numero di voci libera PSRAM/RAM/CPU |
| 2 | **3 voci sintetizzatore** (canali 11/13/14) | oscillatori doppi + inviluppo + ladder filter | medio (RAM1/audio block) | **rimovibile** se vuoi solo sampler → libera RAM1 e audio block |
| 3 | **Polifonia** per voce | più note insieme sulla stessa voce | CPU + PSRAM | abbassare la polifonia max alleggerisce |
| 4 | **ADSR per voce** (Attack/Hold/Decay/Sustain/Release) | inviluppo d'ampiezza | piccolo | difficile da togliere (centrale) |

## 2. Effetti DSP per voce

| # | Feature | A cosa serve | Peso | Alleggeribile? |
|---|---|---|---|---|
| 5 | **Filtro PASS/FREQUENCY** (state-variable) | taglio/cutoff per voce | medio | si può ridurre a meno voci filtrate |
| 6 | **Riverbero** (Freeverb in DMAMEM) | riverbero per voce (canali 1,2,5,6,7,8,11) | **grosso (DMAMEM/CPU)** | **molto alleggeribile**: togliere il riverbero libera parecchia RAM2/CPU |
| 7 | **Bitcrusher** per voce | riduzione bit/sample-rate | piccolo | rimovibile |
| 8 | **Detune** per voce | scordatura fine | piccolo | rimovibile |
| 9 | **Octave** per voce | shift d'ottava | piccolo | rimovibile |
| 10 | **Ladder filter** (voci synth) | filtro Moog sui synth | medio | va via insieme alle voci synth (#2) |

## 3. Sequencer

| # | Feature | A cosa serve | Peso | Alleggeribile? |
|---|---|---|---|---|
| 11 | **Griglia 16×16 "draw"** | disegni le note sulla matrice | core | no (è l'anima dello strumento) |
| 12 | **Pagine di pattern** | più pagine per canzone | RAM (PSRAM/RAM2) | ridurre `maxPages` alleggerisce |
| 13 | **Subpattern** | variazioni dentro un pattern | medio | rimovibile |
| 14 | **Song mode** (64 posizioni × 16 pattern) | arrangiamento di brani | RAM | rimovibile se basta il loop singolo |
| 15 | **Velocity / probabilità / condizione** per step | dinamica e variazione | piccolo | la probabilità/condizione è rimovibile |
| 16 | **Mute** (globale + per-pagina PMOD) | silenziare canali | piccolo | il PMOD per-pagina è rimovibile |
| 17 | **Note shift / copy-paste** | editing veloce | piccolo | rimovibile |
| 18 | **Tap-tempo BPM** | impostare il tempo battendo | minimo | rimovibile |

## 4. Sample / file

| # | Feature | A cosa serve | Peso | Alleggeribile? |
|---|---|---|---|---|
| 19 | **Sample pack + browser SD** | scegliere campioni dalla SD | medio | il browser si può semplificare |
| 20 | **Seek/length/reverse** del campione | trimming e riproduzione inversa | piccolo | rimovibile |
| 21 | **Preview campione** | ascolto in anteprima nel browser | piccolo (`AudioPlaySdWav`) | rimovibile |
| 22 | **Load/Save tracce su SD** | salvare/caricare progetti | medio | core per l'uso reale; difficile togliere |
| 23 | **Registrazione su SD** (`AudioInputI2S`) + **MIC/LINE** | campionare dall'ingresso | medio | **rimovibile** se non registri dal vivo |
| 24 | **Count-in registrazione** | 4 battute prima di registrare | minimo | rimovibile |

## 5. MIDI

| # | Feature | A cosa serve | Peso | Alleggeribile? |
|---|---|---|---|---|
| 25 | **USB MIDI (16 porte)** | suonare/essere suonato da PC | piccolo | si può ridurre a 1 porta |
| 26 | **MIDI clock master/slave** | sync di tempo con altri strumenti | medio | **rimovibile** se suoni da solo |
| 27 | **Transport send/receive** + **sync offset** | start/stop e ritardo di sync | piccolo | rimovibile con #26 |
| 28 | **MIDI note in/out**, voice select (MIDI/KEYS), canale per voce | tastiera/sequencer esterni | piccolo | rimovibile |

## 6. LED / visual

| # | Feature | A cosa serve | Peso | Alleggeribile? |
|---|---|---|---|---|
| 29 | **Matrice 16×16 WS2812** (fino a 2 in catena = 32×16) | display principale | core | no |
| 30 | **2ª striscia LED reattiva** (256 LED, pin 24) | visualizzazione accessoria | RAM2 (DMAMEM) + 1 pin | **rimovibile**: libera il pin 24 e RAM2 |
| 31 | **Luminosità + LED mode** (conteggio/rotazione) | regolazione resa | minimo | semplificabile |

## 7. Sistema

| # | Feature | A cosa serve | Peso | Alleggeribile? |
|---|---|---|---|---|
| 32 | **Persistenza EEPROM + backup SD impostazioni** | ricorda le impostazioni | minimo | core |
| 33 | **Monitor batteria (ADC)** | livello batteria | minimo | **rimovibile** se alimentato via USB |
| 34 | **HUD OLED** (nostro, FLASHMEM) | mostra canale/modo/BPM/vol al posto degli anelli RGB | ~80 byte RAM1 | è il nostro, leggerissimo |

---

## Candidati consigliati per alleggerire (dal più "grasso")

1. **Riverbero (#6)** — il singolo blocco DSP più pesante (DMAMEM + CPU). Toglierlo dà il guadagno maggiore.
2. **Voci synth 11/13/14 (#2, #10)** — se ichosynth ti serve solo come *sampler*, via gli oscillatori/ladder → libera RAM1 (quella stretta) e audio block.
3. **2ª striscia LED (#30)** — libera RAM2 e il pin 24 (utile anche per il cablaggio).
4. **MIDI clock/transport (#26-28)** — se suoni da solo.
5. **Registrazione + MIC/LINE (#23-24)** — se non campioni dal vivo.
6. **Song mode / subpattern / probabilità (#13-15)** — se ti basta il pattern singolo.
7. **Monitor batteria (#33)** — se sempre a USB.

> Nota: la **PSRAM (16,5 MB)** dipende quasi solo dal **numero di voci campione e dalla
> lunghezza/polifonia** (#1, #3). Per ridurre il requisito hardware da 2 chip PSRAM a 1,
> la leva è quella — non gli effetti.
