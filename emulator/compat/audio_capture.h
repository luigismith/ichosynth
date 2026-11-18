// audio_capture.h — host audio-input backend for the emulator: it stands in for the
// SGTL5000's ADC. AudioInputI2S (compat/audio_extra.h) pulls 44.1 kHz mono samples from
// here on every graph update, so the firmware's whole input chain (TŒRN: audioInput ->
// audioInputAmp -> queue1 / peakRec / monitor mix) runs on real audio, as on the board.
//
// The capture device is opened only when needed — never silently in the background:
//   * while a recording is running (AudioRecordQueue::begin() .. end()), or
//   * all the time once the user picks an input device in the menu (TAB -> Ingresso
//     audio), so the input meter and monitoring work before recording, as on hardware.
#ifndef NI404_AUDIO_CAPTURE_H
#define NI404_AUDIO_CAPTURE_H

#include <cstdint>

void ni404_capture_set_device(const char *name); // "" / null = system default
void ni404_capture_set_always(bool on);          // keep the device open (menu choice)
void ni404_capture_request(bool on);             // recording started / stopped
// Audio thread: fill `n` samples at 44.1 kHz (zeros when nothing is captured or the
// device is late). Lock-free, never blocks.
void ni404_capture_pull(int16_t *out, int n);
int  ni404_capture_rate();                       // device rate actually granted (0 = closed)
void ni404_capture_shutdown();
void ni404_capture_test_tone(float hz);          // tests: sine on the input when no device (0 = off)

#endif // NI404_AUDIO_CAPTURE_H
