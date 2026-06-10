**🇮🇹 Italiano** · [🇬🇧 English](DEV_ENVIRONMENT.md)

<div align="center">

# 💻 ichosynth — Ambiente di sviluppo

### Guida completa e aggiornata per Windows e macOS

Tutto il necessario per compilare, modificare e caricare il firmware: dall'IDE alle librerie, fino al primo upload sul Teensy 4.1.

[![Aggiornata: Giugno 2026](https://img.shields.io/badge/Aggiornata-Giugno%202026-2ea44f.svg)](#)
[![Arduino IDE 2.3.x](https://img.shields.io/badge/Arduino%20IDE-2.3.x-00979D.svg)](#)
[![Teensyduino 1.61](https://img.shields.io/badge/Teensyduino-1.61-ee6611.svg)](#)
[![OS: Windows · macOS](https://img.shields.io/badge/OS-Windows%20%C2%B7%20macOS-blue.svg)](#)

</div>

> ⚡ **Hai fretta?** Esiste uno **script che fa tutto da solo** (core Teensy + librerie + patch +
> compile-check). Vai al [capitolo 3](#3--via-rapida-uno-script-fa-tutto). La guida manuale è nei
> capitoli successivi.

---

## 📑 Indice

- [1 · Cosa installiamo](#1--cosa-installiamo)
- [2 · Requisiti](#2--requisiti)
- [3 · Via rapida: uno script fa tutto](#3--via-rapida-uno-script-fa-tutto)
- [4 · Installare Arduino IDE](#4--installare-arduino-ide)
- [5 · Aggiungere il supporto Teensy](#5--aggiungere-il-supporto-teensy)
- [6 · Le librerie](#6--le-librerie)
- [7 · Il passo obbligatorio: ResamplingReader.h](#7--il-passo-obbligatorio-resamplingreaderh)
- [8 · Scaricare il progetto e compilare](#8--scaricare-il-progetto-e-compilare)
- [9 · Strumenti opzionali (Python, Git)](#9--strumenti-opzionali-python-git)
- [10 · Checklist e problemi comuni](#10--checklist-e-problemi-comuni)

---

## 1 · Cosa installiamo

| Componente | Versione | A cosa serve | Obbligatorio |
|---|---|---|---|
| **Arduino IDE** | 2.3.x | scrivere/compilare il firmware | ✅ |
| **Supporto Teensy** (Teensyduino) | 1.61 | aggiunge le schede Teensy all'IDE (+ Teensy Loader) | ✅ |
| **Librerie** | vedi cap. 6 | FastLED **3.9.10**, TeensyPolyphony, ecc. | ✅ |
| **ResamplingReader.h** (patch) | dal repo | evita crash nullptr in riproduzione | ✅ |
| **Python** | 3.12 *(o 3.13+ con `audioop-lts`)* | `wavmaker` (conversione campioni) | opzionale |
| **Git / GitHub CLI** | ultima | clonare e versionare il progetto | opzionale |

> ⚠️ Due trappole che la guida (e lo script) gestiscono per te:
> 1. **FastLED deve essere la 3.9.10** — le 3.10.x si rompono sul percorso WS2812Serial del Teensy.
> 2. Le due librerie **newdigate** (`teensy-variable-playback`, `teensy-polyphony`) vanno prese da
>    **GitHub** (stesso HEAD): le copie del registry Arduino sono disallineate tra loro.

---

## 2 · Requisiti

- **Windows**: Windows 10 o 11, 64 bit. ⚠️ **Non** usare Arduino IDE dal **Microsoft Store**: è
  incompatibile con Teensy. Usa l'installer `.exe`/`.msi` (o winget).
- **macOS**: macOS 10.15 o successivo; supporto nativo **Intel** e **Apple Silicon** (M1/M2/M3/M4). Su
  macOS è supportato **solo** Arduino IDE 2.x.
- **Cavo micro-USB dati** (non solo-carica) per il Teensy 4.1.
- ~1 GB di spazio su disco per IDE + toolchain + librerie.

---

## 3 · Via rapida: uno script fa tutto

Nel repo, in `scripts/`, ci sono due script che installano il core Teensy + tutte le librerie con le
**versioni giuste**, applicano la patch `ResamplingReader.h` e fanno il **compile-check**.

Prima installa **[`arduino-cli`](https://arduino.github.io/arduino-cli/)**, poi lancia lo script:

**Windows (PowerShell):**
```powershell
winget install ArduinoSA.CLI
powershell -ExecutionPolicy Bypass -File scripts\setup-dev-env.ps1
```

**macOS (Terminale):**
```bash
brew install arduino-cli
chmod +x scripts/setup-dev-env.sh
./scripts/setup-dev-env.sh
```

> 💡 Se lo script va a buon fine, salta al [capitolo 8.4](#84-compilare-e-caricare) per l'upload. Se
> preferisci capire ogni passo (o lo script fallisce), continua con la guida manuale qui sotto.

---

## 4 · Installare Arduino IDE

### Windows
**winget** (consigliato): `winget install --id ArduinoSA.IDE --source winget`
oppure scarica l'installer **Windows (.exe/.msi)** da `https://www.arduino.cc/en/software`.

> ⚠️ Errore n°1: **niente Microsoft Store**. Quella versione impedisce al Teensy Loader di funzionare.

### macOS
**Homebrew**: `brew install --cask arduino-ide`
oppure scarica il **.dmg** (universale Intel/Apple Silicon) e trascina l'app in Applicazioni.

> ⚠️ **Gatekeeper**: alla prima apertura usa **tasto destro → Apri** (una volta), oppure Impostazioni →
> Privacy e Sicurezza → "Apri comunque".

---

## 5 · Aggiungere il supporto Teensy

1. Apri Arduino IDE → **File → Preferences** (Windows, `Ctrl+,`) o **Arduino IDE → Settings** (macOS, `Cmd+,`).
2. In **"Additional boards manager URLs"** incolla:
   ```text
   https://www.pjrc.com/teensy/package_teensy_index.json
   ```
3. Apri il **Boards Manager** (icona a sinistra), cerca **"teensy"** e installa
   **"Teensy (for Arduino IDE 2.x.x)"** (1.61). Comparirà anche il **Teensy Loader**.

> ℹ️ **Driver**: su Windows 10/11 e su macOS **non servono driver aggiuntivi**.

Verifica: **Tools → Board → Teensy → Teensy 4.1** è presente? Sei pronto.

---

## 6 · Le librerie

Apri il **Library Manager** (`Ctrl/Cmd+Shift+I`) e installa:

| Cerca | Note |
|---|---|
| **FastLED** | ⚠️ versione **3.9.10** esatta (non la più recente) |
| **Mapf** | mappatura float |
| **Switch** (di Albert van Dalen) | gestione pulsanti/gesti (`avdweb_Switch`) |
| *(solo se usi l'OLED)* **Adafruit SSD1306** + **Adafruit GFX** | schermo opzionale |

Le due librerie **newdigate** non si prendono dal Library Manager (le copie sono disallineate): vanno
installate da GitHub. Il modo più semplice è lo **script** del [capitolo 3](#3--via-rapida-uno-script-fa-tutto);
in alternativa, da `arduino-cli`:
```bash
arduino-cli config set library.enable_unsafe_install true
arduino-cli lib install --git-url https://github.com/newdigate/teensy-variable-playback.git
arduino-cli lib install --git-url https://github.com/newdigate/teensy-polyphony.git
```

> ℹ️ **Già incluse nel core Teensy** (non installarle a parte): `Audio`, `Encoder`, `WS2812Serial`,
> `Wire`, `EEPROM`, `SD`.

---

## 7 · Il passo obbligatorio: ResamplingReader.h

La libreria `teensy-variable-playback` va **patchata** col file fornito nel repo
([`_DOCS/ResamplingReader.h`](_DOCS/ResamplingReader.h)), che previene crash da puntatore nullo.

Sostituisci il file in:
- **Windows**: `Documenti\Arduino\libraries\teensy-variable-playback\src\ResamplingReader.h`
- **macOS**: `~/Documents/Arduino/libraries/teensy-variable-playback/src/ResamplingReader.h`

> ⚠️ Va rifatto **ogni volta che aggiorni** quella libreria. (Lo script del cap. 3 lo fa per te.)

---

## 8 · Scaricare il progetto e compilare

### 8.1 Scaricare
```bash
git clone https://github.com/luigismith/ichosynth.git
```
oppure **Code → Download ZIP** dalla pagina GitHub. Apri `soundpauli_ni404.ino` con Arduino IDE.

### 8.2 Impostazioni di compilazione (menu Tools)
| Voce | Valore |
|---|---|
| **Board** | Teensy 4.1 |
| **USB Type** | **Serial + MIDIx16** |
| **CPU Speed** | 600 MHz (default) |
| **Port** | la porta del Teensy (dopo il collegamento) |

### 8.3 (Build a 3 encoder) config.h
In [`config.h`](config.h) la build a 3 encoder è **già impostata** (`HAS_ENCODER4 0`); lasciala così.
Funzioni opzionali del fork:
```c
#define OLED_ENABLED 1            // schermo OLED di stato
#define MIDI_CLOCK_OUT_ENABLED 1  // MIDI clock out (master sync)
```

### 8.4 Compilare e caricare
1. Collega il Teensy 4.1 via USB (cavo **dati**).
2. **Verify** (✓) per compilare, poi **Upload** (→).
3. Si apre il **Teensy Loader**: di solito programma da solo; se resta in attesa, premi il
   **pulsantino bianco** sul Teensy.
4. A fine flash parte l'animazione sulla matrice LED.

> 💡 La prima compilazione è lenta (build del core); le successive sono rapide.

---

## 9 · Strumenti opzionali (Python, Git)

### 9.1 Python — per il convertitore di campioni `wavmaker`
Nel repo, in `_SDCARD/`, trovi `wavmaker.exe` (GUI Windows, **senza Python**) e i sorgenti
`wavmaker_gui.py` / `wavmaker.py`.

> ⚠️ Lo script Python usa il modulo `audioop`, **rimosso da Python 3.13+**. Soluzioni:
> **(a)** usa **Python 3.12**, oppure **(b)** `pip install audioop-lts`.

**Windows:** `winget install Python.Python.3.12`  · **macOS:** `brew install python@3.12`

### 9.2 Git e GitHub CLI
**Windows:** `winget install Git.Git` (+ `GitHub.cli` opzionale)
**macOS:** `xcode-select --install` (include git) · `brew install gh` (opzionale)

---

## 10 · Checklist e problemi comuni

| ✓ | Controllo |
|---|---|
| ☐ | Arduino IDE ≥ 2.3.x si avvia |
| ☐ | Tools → Board → Teensy → Teensy 4.1 presente |
| ☐ | FastLED installata è la **3.9.10** |
| ☐ | Le due librerie newdigate da GitHub installate |
| ☐ | `ResamplingReader.h` sostituito |
| ☐ | USB Type = Serial + MIDIx16 |
| ☐ | `soundpauli_ni404.ino` compila senza errori |

| Sintomo | Causa / soluzione |
|---|---|
| Teensy non compare in Boards Manager | URL non salvato nelle Preferences; riavvia l'IDE |
| "Teensy Loader is unable to…" (Windows) | hai l'IDE del Microsoft Store → usa l'installer ufficiale |
| Errori `RGB_ORDER` / template in FastLED | FastLED non è la 3.9.10 (declassa a 3.9.10) |
| Errori `AudioPlaySdResmp` / `playRaw` / `override` | le librerie newdigate sono quelle del registry → installale da GitHub |
| Errori `nullptr` / ResamplingReader | patch del cap. 7 non applicata |
| `'usbMIDI' was not declared` | USB Type non su Serial + MIDIx16 |
| macOS: "operazione non consentita" sulle librerie | ridai il permesso a Documenti da Privacy e Sicurezza |
| Porta non visibile | cavo USB solo-carica → usa un cavo dati |

---

<div align="center">

*Parte del progetto **[ichosynth](README.it.md)** · fork di NI404 (SP_) · per il workshop ICHOS 2026.*

</div>
