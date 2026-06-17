// audio_capture.h — host audio-input backend for the emulator. Captures from an
// SDL audio input device (mono, 16-bit, 44100 Hz, in 128-sample blocks) so the
// AudioRecordQueue shim can feed the firmware's recording path real audio. On
// real hardware this layer doesn't exist (the Teensy AudioRecordQueue is fed by
// AudioInputI2S); here it bridges the selected input device into the same API.
#ifndef NI404_AUDIO_CAPTURE_H
#define NI404_AUDIO_CAPTURE_H

#include <cstdint>

void ni404_capture_set_device(const char *name); // "" / null = default device
void ni404_capture_start();                       // open + start capturing
void ni404_capture_stop();                        // stop + close
int  ni404_capture_available();                   // 128-sample blocks ready
bool ni404_capture_read(int16_t *out128);         // pop one 128-sample block

#endif // NI404_AUDIO_CAPTURE_H
