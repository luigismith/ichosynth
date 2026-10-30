# legacy/ — the NI404 roots

ichosynth began as a fork of **NI404** by **SP_ (soundpauli)**. The product today is the **TŒRN
port** (see the [main README](../README.md)). What's here is kept only as a reference and as a
fallback build. It is **not** needed to build an ichosynth.

| Folder | What | Used by |
|---|---|---|
| [`soundpauli_ni404/`](soundpauli_ni404) | the NI404-based "bench" firmware (4 encoders + OLED hybrid) | the `ni404emu` target of the [desktop emulator](../emulator/MANUALE.md) and its CI build |
| [`ni404_pcb/`](ni404_pcb) | SP_'s original NI404 PCB (KiCad project, Gerbers, BOM) | nothing: reference only |
| [`ni404_enclosure/`](ni404_enclosure) | SP_'s original NI404 enclosure (STL, DXF, Fusion 360) | nothing: the ichosynth case is in [`case/`](../case) |

The folder is named `soundpauli_ni404/` so that the Arduino IDE can open
`soundpauli_ni404.ino` directly. All of this keeps SP_'s original credit and MIT license.
