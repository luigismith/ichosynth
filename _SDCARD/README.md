# ichosynth — contenuto della micro SD (sample set di fabbrica)

Questa cartella è l'**immagine della micro SD** da inserire nel Teensy 4.1.
Copia tutto il contenuto di `_SDCARD/` nella **radice** della scheda
(FAT32). Il firmware TŒRN legge i campioni da qui.

## Come il firmware organizza i campioni

Il firmware ha **due** sistemi, con due layout diversi:

### 1. Samplepack — `<pack>/<voce>.wav`
Un *samplepack* è una cartella numerata (`0`…`99`). Contiene **8 file**, uno
per voce campione: `1.wav` … `8.wav` (canali 1-8). All'avvio, e ogni volta che
selezioni un pack, il firmware carica l'intero pack in PSRAM.

> Formato obbligatorio: **WAV PCM, MONO, 16-bit, 44100 Hz**. Altri formati non
> vengono caricati.

Pack inclusi (stessa mappa voci per tutti: KICK / SNARE / HAT chiuso / HAT
aperto / CLAP / TOM / PERC / PERC):

| Pack | Kit | Macchina |
|------|-----|----------|
| `0/` | **kit di fabbrica** (= 808) | copia del pack 1, così un'unità vergine suona subito |
| `1/` | 808 | Akai ASR-X (campioni 808) |
| `2/` | Drumulator | E-mu Drumulator |
| `3/` | SpecDrum | Cheetah SpecDrum |
| `4/` | DP50 | Technics PCM DP50 |
| `5/` | Soviet | Rokton UDS + Lel-DR8 |

### 2. Sample browser — `samples/<categoria>/<nome>.wav`
File WAV liberi (fino a 999) che sfogli da **SET_WAV** per assegnarli a una
voce. Stesso formato (mono/16-bit/44100). Qui sono ordinati per categoria:

```
samples/kick   samples/snare  samples/hat   samples/clap
samples/tom    samples/perc   samples/fx
```

## Origine e licenza dei campioni

Tutti i campioni provengono dalla raccolta **drum_sklad** di Pavel Semiletov
(<https://github.com/psemiletov/drum_sklad>), rilasciata come
**public domain**: *"This is free and unencumbered samples released into the
public domain."* Possono quindi essere ridistribuiti liberamente in questo
repo, anche a scopo commerciale, senza attribuzione.

## Rigenerare il set

Lo script scarica i sorgenti, li converte nel formato corretto e li ordina:

```sh
python _SDCARD/build_samples.py            # scarica + converte + ordina
python _SDCARD/build_samples.py --no-clean # non rimuove i vecchi file _N.wav
```

Il convertitore è in puro Python (nessun ffmpeg): legge WAV PCM 8/16/24/32-bit,
float e WAVE_FORMAT_EXTENSIBLE, mixa a mono, ricampiona a 44100 Hz e scrive
WAV mono/16-bit con header standard da 44 byte.

> Nota: i vecchi file in formato NI404 (`_<n>.wav`, es. `_1.wav`, `_300.wav`) sono
> stati rimossi — il firmware TŒRN cerca `1.wav`, non `_1.wav`. Se ne ricompaiono
> (da una vecchia SD), `python _SDCARD/build_samples.py` li elimina.

## Aggiungere campioni tuoi

Usa l'app **`wavmaker`** (GUI `wavmaker.exe` / `wavmaker_gui.py`, o CLI `wavmaker.py`):
converte qualsiasi WAV in mono/16-bit/44100 e lo scrive nel posto giusto. Due modalità:

- **Samplepack**: scegli fino a 8 WAV → diventano `<pack>/1.wav` … `8.wav` (crea una
  cartella `6/`…`99/`). Da riga di comando: `python _SDCARD/wavmaker.py --pack 6 <cartella>`.
- **Libreria browser**: i WAV vanno in `samples/<categoria>/<nome>.wav` mantenendo i nomi.
  Da riga di comando: `python _SDCARD/wavmaker.py <cartella>` (converte sul posto).
