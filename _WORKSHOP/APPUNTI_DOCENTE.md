# 🎓 Appunti del docente — giornata di costruzione

### ichosynth · ICHOS 2026 · Taranto · 12 giugno 2026

> Foglio sintetico da tenere a portata di mano. Le note dettagliate sono anche
> nelle **note di ogni slide** (Visualizza relatore in PowerPoint).

**Obiettivo della giornata:** ogni partecipante assembla l'ichosynth e arriva al
**primo suono** in cuffia.

---

## ⏱️ Scaletta a tempo (indicativa)

| Ora | Blocco | Slide |
|---|---|---|
| 09:00 | Accoglienza · componenti sul banco · **sicurezza** | 1–6 |
| 10:00 | **Mappa pin** + inizio cablaggio | 7 |
| 11:00 | *pausa* | |
| 11:15 | Montaggio **Fasi 1–3** (Teensy · audio · LED) | 8–10 |
| 13:00 | *pranzo* | |
| 14:00 | Montaggio **Fasi 4–6** (encoder · filtro/OLED · controllo) | 11–13 |
| 15:30 | **Firmware** (flasher) + **SD** | 14–15 |
| 16:15 | *pausa* | |
| 16:30 | **Primo avvio**, filtro, diagnosi | 16–18 |
| 17:15 | Chiusura | 19 |

> Adatta i tempi al ritmo del gruppo. Regola d'oro: **nessuno dà tensione** finché
> non ha superato il controllo col multimetro (Fase 6).

---

## 🗣️ Cosa dire / far fare, fase per fase

- **Sicurezza (sl. 6):** mai cablare sotto tensione · check 5V/3,3V/GND · multimetro = niente corti · saldature lucide. *Saldatura "fredda" = causa #1 di guasti.*
- **Mappa pin (sl. 7):** è LA referenza, tenetela aperta tutto il giorno.
- **Fase 1 — Teensy:** PSRAM già montata (la fornite); loro saldano gli header; USB → riconosciuto.
- **Fase 2 — Audio:** *impilare* è più semplice (i segnali si collegano da soli).
- **Fase 3 — LED:** la **freccia di INGRESSO** va al pin **17**; bassa luminosità → USB basta.
- **Fase 4 — Encoder:** la più lunga; **etichettare i fili**; CLK/DT incrociati = gira al contrario.
- **Fase 5 — Filtro/OLED:** pulsante 41→GND (2 fili); OLED in parallelo sull'I2C audio.
- **Fase 6 — Controllo:** multimetro su tutti i banchi *prima* di accendere.
- **Firmware (sl. 14):** `flasher.exe` → Flash → **premi PROGRAM**. SmartScreen: *Esegui comunque*.
- **SD (sl. 15):** `wavmaker.exe` → Scansiona → Converti.
- **Primo avvio (sl. 16):** SD+cuffie+USB → logo → cursore → nota → Play.

---

## 🚨 Errori da intercettare (i 6 più frequenti)

1. **Cavo USB solo-carica** → non riconosciuto. Tenete un cavo dati di scorta.
2. **PSRAM** mal saldata / alimentazione debole → riavvii.
3. **Board nuda senza SD si riavvia da sola** — è normale: con la SD inserita smette. *(Non è un guasto.)*
4. **DIN sul pin sbagliato** o freccia LED invertita → niente luci.
5. **CLK/DT incrociati** → encoder al contrario (si scambiano i due fili).
6. **Niente suono** → scheda audio non a posto o cuffie/volume.

---

## 🧰 Preparazione banco (prima dell'inizio)

- Teensy **con PSRAM già saldata** per ciascuno.
- Cavi USB **dati** testati · alimentatori 5V ≥ 2A.
- micro SD **FAT32** + cuffie per ogni postazione.
- PC con **`flasher.exe`** e **`wavmaker.exe`** pronti (+ `ichosynth.hex`).
- Multimetri, saldatori, terza mano, flussante, alcol isopropilico.

---

<div align="center">

*Buona giornata di costruzione. Quando suona → Manuale d'Uso.*

</div>
