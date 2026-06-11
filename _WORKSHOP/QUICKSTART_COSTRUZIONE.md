# 🛠️ ichosynth — Quick-start da banco

### Guida rapida di costruzione · ICHOS 2026 · Taranto

> Tienila accanto al banco. Spunta ogni casella man mano. La guida completa è nel
> **Manuale di Costruzione**; qui c'è solo l'essenziale per montare e accendere.

---

## ✅ 1 · Componenti sul banco (BOM)

- [ ] **Teensy 4.1** con **PSRAM** (2× 8 MB) già saldata — *obbligatoria*
- [ ] **Teensy Audio Adaptor Rev D** (codec SGTL5000 + jack 3,5 mm)
- [ ] **Matrice LED WS2812B 16×16** (256 LED)
- [ ] **3 encoder KY-040** (SINISTRA · CENTRALE · DESTRA)
- [ ] **1 pulsante** momentaneo (filtro lowpass)
- [ ] **micro SD** Class 10, ≤ 32 GB, **FAT32**
- [ ] **cavo micro-USB dati** + alimentatore 5V ≥ 2A
- [ ] **cuffie** con jack 3,5 mm (niente altoparlanti a bordo)
- [ ] cavetti Dupont, pin header, *(opz.)* **OLED SSD1306 0,96" I2C**

---

## 📌 2 · Mappa pin (la "verità" del firmware)

```
LED matrix DIN ........... 17          Audio MCLK ... 23    Audio SDA ... 18
                                       Audio BCLK ... 21    Audio SCL ... 19
Encoder SINISTRA  CLK 5  DT 22  SW 15  Audio LRCLK .. 20
Encoder CENTRALE  CLK 9  DT 14  SW 16  Audio TX ..... 7
Encoder DESTRA    CLK 4  DT 2   SW 3   Audio RX ..... 8
Pulsante FILTRO ... pin 41  →  GND     OLED ......... SDA 18 / SCL 19 (0x3C)
```

⚡ **Alimentazioni:** matrice = **5V** · encoder/OLED/audio = **3,3V** · **GND sempre in comune.**
Encoder: pin **"+" → 3,3V**, **GND → GND**. Il 4° encoder **non si monta** (pin 32/33 liberi).

---

## 🔌 3 · Montaggio passo-passo

**Fase 1 — Teensy**
- [ ] PSRAM saldata (o Teensy che la ha già) · header saldati
- [ ] collega USB → il PC lo riconosce

**Fase 2 — Scheda audio**
- [ ] **impila** la scheda audio sul Teensy (più semplice) *oppure* cabla i segnali (7,8,20,21,23,18,19)
- [ ] cuffie nel jack 3,5 mm

**Fase 3 — Matrice LED**
- [ ] trova la **freccia di INGRESSO** dati → pin **17** (l'uscita resta libera)
- [ ] **5V** e **GND** della matrice

**Fase 4 — Encoder ×3** (SINISTRA → CENTRALE → DESTRA)
- [ ] per ognuno: CLK, DT, SW come da mappa + "+" (3,3V) e GND
- [ ] etichetta i fili: **incrociare CLK/DT è l'errore #1** (gira al contrario → si scambiano)

**Fase 5 — Pulsante FILTRO e OLED (opz.)**
- [ ] pulsante: un capo a **41**, l'altro a **GND** (pull-up interno, niente resistenze)
- [ ] OLED in parallelo su SDA 18 / SCL 19, VCC 3,3V, GND

**Fase 6 — Controllo prima di accendere** 🔴
- [ ] multimetro: **nessun corto** 5V–GND e 3,3V–GND
- [ ] 5V / 3,3V / GND nei pin giusti

---

## ⚡ 4 · Caricare il firmware (flasher in un clic)

- [ ] collega il Teensy via USB
- [ ] apri **`_FLASHER/flasher.exe`** (al primo avvio Windows SmartScreen → *Ulteriori informazioni → Esegui comunque*)
- [ ] premi **⚡ Flash ichosynth**
- [ ] quando l'app lo chiede, premi una volta il **pulsantino PROGRAM** sul Teensy
- [ ] attendi *"Firmware scritto e Teensy riavviato"* ✅

> Niente Arduino/arduino-cli per chi flasha: il firmware è già dentro l'app.

---

## 💾 5 · Preparare la SD (campioni)

- [ ] apri **`_SDCARD/wavmaker.exe`** → **🔍 Scansiona** la SD (crea/formatta la struttura se serve)
- [ ] **Aggiungi file/cartella** WAV → **Converti** (diventano mono · 16-bit · 44.1 kHz, nominati `_<n>.wav`)
- [ ] struttura finale: `samples/0/_1.wav … _99.wav`, `samples/1/_100.wav …`

---

## ▶️ 6 · Primo avvio

- [ ] SD inserita · cuffie · alimenta via USB → **logo** sulla matrice
- [ ] icona **noSD** rossa? spegni, inserisci la SD, riaccendi
- [ ] **SINISTRA / DESTRA**: muovi il cursore (puntino bianco)
- [ ] **push CENTRALE**: piazza una nota → senti il campione
- [ ] **doppio click CENTRALE**: Play/Pausa
- [ ] **tieni il pulsante FILTRO + gira la CENTRALE**: il suono si scurisce (lowpass)

---

## 🆘 7 · Se qualcosa non va (top 5)

| Sintomo | Rimedio rapido |
|---|---|
| Non riconosciuto dal PC | cavo USB **dati** (non solo-carica); ricontrolla header / corto 5V-GND |
| Si riavvia da solo | PSRAM mancante/mal saldata; alimentazione 5V ≥ 2A; **SD inserita** |
| LED spenti / colori errati | DIN non sul **17**; freccia dati invertita; GND non comune |
| Encoder "al contrario" | inverti **CLK e DT** di quell'encoder |
| Nessun suono | scheda audio (7,8,20,21,23,18,19); cuffie; volume |

---

<div align="center">

**Quando suona → Manuale d'Uso.** Buona costruzione! 🎛️
*ichosynth · fork di NI404 (SP_) · firmware MIT*

</div>
