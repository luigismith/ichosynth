// waveheaderparser.h — minimal stub of the newdigate WAV header parser. The
// NI404 firmware plays sample voices via playRaw(int16* array, ...), so the
// ResamplingReader::play(filename) path that uses this parser is never
// instantiated. These declarations exist only so ResamplingReader.h compiles.
#ifndef NI404_NEWDIGATE_WAVEHEADERPARSER_H
#define NI404_NEWDIGATE_WAVEHEADERPARSER_H

#include <cstdint>

struct wav_header {
    uint16_t audio_format = 1;
    uint16_t num_channels = 1;
    uint32_t sample_rate = 44100;
    uint16_t bit_depth = 16;
};

struct wav_data_header {
    uint32_t data_bytes = 0;
};

class WaveHeaderParser {
public:
    bool readWaveHeaderFromBuffer(const char *, wav_header &h) { h.bit_depth = 16; h.num_channels = 1; return true; }
    bool readInfoTags(const unsigned char *, int, unsigned &size) { size = 0; return true; }
    bool readDataHeader(const unsigned char *, int, wav_data_header &d) { d.data_bytes = 0; return true; }
};

#endif
