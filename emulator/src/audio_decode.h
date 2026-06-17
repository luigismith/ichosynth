// audio_decode.h — decode any common source audio file to mono float, so the
// sample importer accepts more than WAV. Backed by the dr_libs single-header
// decoders (public domain): WAV, MP3 and FLAC. No external/runtime dependency.
#ifndef NI404_AUDIO_DECODE_H
#define NI404_AUDIO_DECODE_H

#include <vector>

// Decode `path` (wav/mp3/flac, any rate/channels) into `mono` (samples in
// [-1,1], channels averaged) and report its sample `rate`. Returns true on
// success; on failure returns false and writes a short reason into err.
bool ni404_decode_audio(const char *path, std::vector<float> &mono,
                        unsigned int &rate, char *err, int errlen);

// Comma-separated list of importable extensions, for UI hints (e.g. "wav, mp3, flac").
const char *ni404_decode_formats();

#endif // NI404_AUDIO_DECODE_H
