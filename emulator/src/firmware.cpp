// firmware.cpp — integrates the REAL NI404 device firmware into the emulator.
//
// The unmodified sketch (../soundpauli_ni404.ino) is compiled as part of this
// translation unit. It defines setup(), loop(), the audio graph (audioinit.h),
// the LED array `leds[]`, the sequencer, modes, MIDI handlers — everything. The
// compat/ shims satisfy every Teensy/Arduino API it touches.
//
// The frontend calls ni404_setup() once and ni404_loop() each frame; we forward
// to the firmware's setup()/loop() and pump the IntervalTimers (the sequencer
// clock playTimer + the MIDI-clock timer) which on hardware fire from an ISR.
#include "ni404_host.h"
#include "IntervalTimer.h"
#include "ni404_prototypes.h"   // Arduino-style forward declarations (auto-generated)

#include "soundpauli_ni404.ino"

#include "sample_import.h"
#include <filesystem>
#include <string>
#include <cctype>
#include <cstring>

#ifndef NI404_SDCARD_PATH
#define NI404_SDCARD_PATH "_SDCARD"
#endif

// Drag-and-drop sample loader: convert a dropped WAV to the kit format (16-bit
// mono 44.1 kHz), install it on the virtual SD under folder 9 (_900.._999 =
// user imports) at the next free id, then load it into the current channel so
// it's auditioned immediately and stays in the library for the file browser.
const char *ni404_import_sample(const char *srcPath) {
    static char status[96];
    namespace fs = std::filesystem;

    // Accept any supported source format (wav/mp3/flac); the converter decodes it.
    std::string s = srcPath ? srcPath : "";
    std::string low = s;
    for (char &ch : low) ch = (char)std::tolower((unsigned char)ch);
    auto endsWith = [&](const char *e) { size_t n = std::strlen(e);
        return low.size() >= n && low.compare(low.size() - n, n, e) == 0; };
    if (!endsWith(".wav") && !endsWith(".mp3") && !endsWith(".flac")) {
        std::snprintf(status, sizeof status, "Formato non supportato (wav/mp3/flac)");
        return status;
    }

    // Ensure folder 9 exists and find the first free id 901..999.
    std::error_code ec;
    fs::path dir = fs::path(NI404_SDCARD_PATH) / "9";
    fs::create_directories(dir, ec);
    int id = 0;
    for (int slot = 1; slot <= 99; slot++) {
        fs::path cand = dir / ("_" + std::to_string(900 + slot) + ".wav");
        if (!fs::exists(cand)) { id = 900 + slot; break; }
    }
    if (id == 0) { std::snprintf(status, sizeof status, "Import folder full (901-999)"); return status; }

    fs::path dst = dir / ("_" + std::to_string(id) + ".wav");
    char err[64] = {0};
    if (!ni404_wav_to_kit(srcPath, dst.string().c_str(), err, sizeof err)) {
        std::snprintf(status, sizeof status, "Import failed: %s", err);
        return status;
    }

    // Load into the current channel (clamp to a valid sample channel 1..8).
    unsigned int ch = SMP.currentChannel;
    if (ch < 1 || ch > 8) ch = (SMP.y >= 2 && SMP.y <= 9) ? (SMP.y - 1) : 1;
    SMP.currentChannel = ch;
    SMP.seek = 0; SMP.seekEnd = 0;
    loadSample(0, id);
    SMP.mute[ch] = false;

    std::snprintf(status, sizeof status, "Imported _%d  ->  channel %u", id, ch);
    return status;
}

// ---- "play it" verification hooks (drive the real sound engine) ------------
// Load a kit sample id (e.g. 302 = closed hat) into a channel.
void ni404_load_sample(int channel, int id) {
    if (channel < 1 || channel > 8) return;
    SMP.currentChannel = (unsigned int)channel; SMP.seek = 0; SMP.seekEnd = 0;
    loadSample(0, id);
    SMP.mute[channel] = false;
}

// ---- SD-card management hooks (emulator) ----------------------------------
const char *ni404_sd_root() { static std::string s; s = SD.getRoot(); return s.c_str(); }
const char *ni404_sd_default_root() { static std::string s; s = SDClass::resolve_root(); return s.c_str(); }
int ni404_current_channel() { return (int)SMP.currentChannel; }

bool ni404_sd_set_root(const char *path) {
    if (!path || !*path) return false;
    SD.setRoot(path);
    // Reload the sample pack from the new folder so the change is audible.
    loadSamplePack(samplePackID);
    return true;
}
// Play a sample channel (1..8) like a MIDI keyboard note (pitch 60 = base).
void ni404_play_note(int channel, int pitch, int vel) {
    if (channel < 1 || channel > 8) return;
    SMP.y = (unsigned int)(channel + 1);   // handleNoteOn plays _samplers[SMP.y-1]
    handleNoteOn(1, (uint8_t)pitch, (uint8_t)vel);
}
// Play a synth voice (13 or 14) at pianoFrequencies[row] (row 1..16).
void ni404_play_synth(int voice, int row, int vel) {
    if (row < 1 || row > 16) return;
    float amp = mapf(vel, 1, 127, 0.0, 1.0);
    if (voice == 13) { sound13.frequency(pianoFrequencies[(row - 1) & 15] / 2.0f); sound13.amplitude(amp); envelope13.noteOn(); }
    else if (voice == 14) { sound14.frequency(pianoFrequencies[row & 15] / 2.0f); sound14.amplitude(amp); envelope14.noteOn(); }
    startTime = millis(); noteOnTriggered = true;
}
// Set a channel's filter cutoff knob (1..maxfilterResolution) and apply it.
void ni404_set_filter(int channel, int knob) {
    if (channel < 1 || channel >= (int)maxFilters) return;
    if (knob < 1) knob = 1; if (knob > (int)maxfilterResolution) knob = (int)maxfilterResolution;
    SMP.filter_knob[channel] = (unsigned int)knob;
    applyFilter((unsigned int)channel);
}
void ni404_set_crush(int channel, int bits) {
#if BITCRUSH_ENABLED
    if (channel < 1 || channel >= (int)maxCrush) return;
    if (bits < 1) bits = 1; if (bits > 16) bits = 16;
    crushBits[channel] = (uint8_t)bits;
    applyCrush((unsigned int)channel);
#else
    (void)channel; (void)bits;
#endif
}
int  ni404_test_beat()    { return (int)beat; }
int  ni404_test_page()    { return (int)SMP.page; }
int  ni404_test_playing() { return isPlaying ? 1 : 0; }
int  ni404_test_bpm()     { return (int)SMP.bpm; }
// Editing state read-back (the grid-cursor + placed notes the firmware sees).
int  ni404_test_cursor_x()  { return (int)SMP.x; }
int  ni404_test_cursor_y()  { return (int)SMP.y; }
int  ni404_test_edit_page() { return (int)SMP.edit; }
const char *ni404_test_mode() { static std::string s; s = currentMode->name.c_str(); return s.c_str(); }
int  ni404_test_note_at(int step, int row) {
    if (step < 1 || step >= (int)maxlen || row < 1 || row > (int)maxY) return -1;
    return (int)note[step][row][0];
}

void ni404_setup() {
    setup();
}

void ni404_loop() {
    loop();
    ni404_pump_timers();
}

// ---- headless verification hooks ------------------------------------------
// Load samples/0/_1.wav into `channel` (samples load on demand on the device),
// then play it exactly as an incoming MIDI note would, via handleNoteOn().
void ni404_test_trigger(int channel) {
    SMP.currentChannel = (unsigned int)channel;
    SMP.seek = 0;
    SMP.seekEnd = 0;
    loadSample(0, 1);                      // samples/0/_1.wav -> this channel
    SMP.y = (unsigned int)(channel + 1);   // handleNoteOn plays _samplers[SMP.y-1]
    handleNoteOn(1, 60, 100);              // pitch 60 = base note, velocity 100
}

// After a trigger, is this channel's resampling voice actually playing?
int ni404_test_sample_len(int channel) {
    if (channel < 0 || channel >= 13) return 0;
    return _samplers[channel].isPlaying() ? 1 : 0;
}

// Peak (0..32767) of the raw int16 sample data loaded into a channel — to tell a
// quiet/garbled load apart from a quiet playback path.
int ni404_test_data_peak(int channel) {
    if (channel < 0 || channel >= (int)maxFiles) return 0;
    const int16_t *d = (const int16_t *)sampled[channel];
    int n = (int)(sizeof(sampled[channel]) / 2); if (n > 60000) n = 60000;
    int pk = 0;
    for (int i = 0; i < n; i++) { int a = d[i]; if (a < 0) a = -a; if (a > pk) pk = a; }
    return pk;
}

// Demo song — a 4-page (64-step) arrangement that exercises the whole instrument:
// all 8 drum/perc samples, BOTH melodic synth voices (ch13 sawtooth bass, ch14
// lead), sample pitch-by-row, a vi-IV-I-V chord change per page (Am - F - C - G),
// per-channel filtering and velocity dynamics, building intro -> groove -> peak ->
// turnaround. It plays as a 4-bar loop the moment the emulator starts (--demo).
//
// The grid is note[step][row]: one note per cell. Drums sit on their HOME row
// (row = channel+1, natural pitch); the synth voices pick a pitch from
// pianoFrequencies[] by row (ch13 = row-1, ch14 = row). To avoid same-cell
// clashes the parts are kept in separate row bands: drums rows 2-9, bass rows
// 1-6 (only on the clean downbeats 1 & 9), lead rows 10-15 (above everything).
static void dCell(int step, int row, int chan, int vel) {
    if (step >= 1 && step < (int)maxlen && row >= 1 && row <= (int)maxY) {
        note[step][row][0] = chan; note[step][row][1] = vel;
    }
}
static void dDrum(int step, int ch, int vel) { dCell(step, ch + 1, ch, vel); }  // home row, natural pitch
static void dBass(int step, int k, int vel)  { dCell(step, k + 1, 13, vel); }   // ch13 -> pianoFrequencies[k]
static void dLead(int step, int k, int vel)  { dCell(step, k,     14, vel); }   // ch14 -> pianoFrequencies[k]

void ni404_demo() {
    // Kit into channels 1-8: 1 kick 2 snare 3 closed-hat 4 open-hat 5 clap
    // 6 tom 7 cowbell 8 saw-stab(tonal). (folder 3, made by gen_samples.)
    const int kit[8] = { 300, 301, 302, 303, 304, 306, 307, 310 };
    for (int c = 1; c <= 8; c++) { SMP.currentChannel = (unsigned)c; SMP.seek = 0; SMP.seekEnd = 0; loadSample(0, kit[c - 1]); }

    // Soften the lead (triangle) for a sweeter melody; keep the rich saw bass.
    sound14.begin(WAVEFORM_TRIANGLE);

    // Per-channel filters: mostly wide open, but roll the saw-stab and tom back
    // for warmth — an audible demo of the per-voice lowpass.
    for (unsigned int c = 1; c < maxFilters; c++) SMP.filter_knob[c] = maxfilterResolution;
    SMP.filter_knob[8] = 12;   // saw stab: warm / filtered
    SMP.filter_knob[6] = 20;   // tom: slightly mellow
    applyAllFilters();

    // Clear every page.
    for (unsigned int x = 1; x < maxlen; x++) for (unsigned int y = 1; y <= maxY; y++) { note[x][y][0] = 0; note[x][y][1] = 0; }

    const int bassRoot[4] = { 5, 3, 0, 4 };   // Am F C G — pianoFrequencies index (low octave)
    for (int page = 0; page < 4; page++) {
        const int base = page * 16;

        // --- kick: four-on-floor, downbeats accented; extra push from page 2 ---
        const int kickS[4] = { 1, 5, 9, 13 };
        for (int i = 0; i < 4; i++) dDrum(base + kickS[i], 1, (kickS[i] == 1 || kickS[i] == 9) ? 122 : 112);
        if (page >= 1) dDrum(base + 11, 1, 100);

        // --- closed hat: offbeat 8ths always + 16th ghosts once the groove fills ---
        const int hatS[4] = { 3, 7, 11, 15 };
        for (int i = 0; i < 4; i++) dDrum(base + hatS[i], 3, 60);
        if (page >= 1) { const int gh[4] = { 4, 8, 12, 16 }; for (int i = 0; i < 4; i++) dDrum(base + gh[i], 3, 30); }

        // --- snare backbeat (from page 2) ---
        if (page >= 1) { dDrum(base + 5, 2, 108); dDrum(base + 13, 2, 108); }

        // --- clap layer + open hat + tonal saw stab (from page 3 = peak) ---
        if (page >= 2) {
            dDrum(base + 5, 5, 80);  dDrum(base + 13, 5, 80);   // clap   (row 6)
            dDrum(base + 7, 4, 48);  dDrum(base + 15, 4, 48);   // open hat (row 5)
            dDrum(base + 3, 8, 58);  dDrum(base + 11, 8, 58);   // saw stab A3 (row 9, natural pitch)
        }

        // --- tom turnaround fill on the last page ---
        if (page == 3) { dDrum(base + 13, 6, 70); dDrum(base + 14, 6, 82); dDrum(base + 15, 6, 94); dDrum(base + 16, 6, 106); }

        // --- sawtooth bass (ch13): chord root on the two downbeats ---
        dBass(base + 1, bassRoot[page], 98);
        dBass(base + 9, bassRoot[page], 92);

        // --- lead melody (ch14), C-major, rows 10-15 — evolves per page ---
        switch (page) {
            case 0: { const int m[][3] = {{1,12,80},{7,11,72},{11,12,82},{15,14,86}};
                      for (auto &n : m) dLead(base + n[0], n[1], n[2]); } break;
            case 1: { const int m[][3] = {{1,10,82},{5,12,78},{7,11,74},{11,14,86},{13,12,80},{15,11,76}};
                      for (auto &n : m) dLead(base + n[0], n[1], n[2]); } break;
            case 2: { const int m[][3] = {{1,14,92},{3,12,80},{5,11,82},{7,14,88},{9,15,96},{11,14,86},{13,12,82},{15,11,80}};
                      for (auto &n : m) dLead(base + n[0], n[1], n[2]); } break;
            case 3: { const int m[][3] = {{1,11,86},{5,13,84},{9,11,82},{11,12,84},{13,11,80},{15,15,90}};
                      for (auto &n : m) dLead(base + n[0], n[1], n[2]); } break;
        }
    }

    // Strong output with a little headroom (the peak with all voices aligned sits
    // near full scale), ~122 BPM, loop all four pages.
    SMP.vol = 9; sgtl5000_1.volume(0.9f);
    SMP.bpm = 122;
    playNoteInterval = ((60 * 1000 / SMP.bpm) / 4) * 1000;
    playTimer.update(playNoteInterval);
    lastPage = 4; SMP.page = 1; beat = 1; pagebeat = 1;
    for (unsigned int p = 0; p <= maxPages; p++) hasNotes[p] = (p >= 1 && p <= 4);
    isPlaying = true;
}
