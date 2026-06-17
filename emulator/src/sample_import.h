// sample_import.h — host-side sample importer. Converts a source audio file
// (WAV/MP3/FLAC via audio_decode, any rate/channels) into the format the
// NI404/toern firmware expects: 16-bit mono PCM at 44100 Hz with a standard
// 44-byte header. Used by the drag-and-drop / browser sample loader.
#ifndef NI404_SAMPLE_IMPORT_H
#define NI404_SAMPLE_IMPORT_H

// Read `src` (any common WAV) and write a 16-bit mono 44.1 kHz WAV to `dst`.
// Returns true on success; on failure returns false and writes a short reason
// into errbuf (if provided).
bool ni404_wav_to_kit(const char *src, const char *dst, char *errbuf, int errlen);

#endif // NI404_SAMPLE_IMPORT_H
