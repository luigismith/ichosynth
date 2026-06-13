// audio_play_array_resmp.h — desktop port of newdigate teensy-variable-playback's
// AudioPlayArrayResmp: a resampling sample-playback voice (AudioStream source)
// built on ResamplingReader. The NI404 firmware drives it via playRaw() +
// setPlaybackRate() (pitch), with linear interpolation.
#ifndef NI404_NEWDIGATE_AUDIO_PLAY_ARRAY_RESMP_H
#define NI404_NEWDIGATE_AUDIO_PLAY_ARRAY_RESMP_H

#include "Audio.h"
#include "newdigate/loop_type.h"
#include "newdigate/interpolation.h"
#include "newdigate/waveheaderparser.h"
#include "newdigate/ResamplingReader.h"
#include <cstring>

// Dummy "file" type for the ResamplingReader template. The firmware only uses
// the in-RAM playRaw() path, so the file-based play() path is never
// instantiated; this just satisfies the template signatures.
struct DummyArrayFile {
    explicit operator bool() const { return false; }
    long size() { return 0; }
    int  read(void *, int) { return 0; }
    void seek(long) {}
    void close() {}
};

class ArrayResamplingReader : public newdigate::ResamplingReader<int16_t, DummyArrayFile> {
public:
    DummyArrayFile open(char *) override { return DummyArrayFile(); }
    int16_t *createSourceBuffer() override { return (int16_t *)this->_sourceBuffer; }
    void close() override {}
    int16_t getSourceBufferValue(long index) override {
        if (!this->_sourceBuffer) return 0;
        int32_t n = this->_file_size / 2;
        if (index < 0 || index >= n) return 0;
        return ((int16_t *)this->_sourceBuffer)[index];
    }
};

class AudioPlayArrayResmp : public AudioStream {
public:
    AudioPlayArrayResmp() : AudioStream(0, nullptr) { reader.begin(); }

    void enableInterpolation(bool enable) {
        reader.setInterpolationType(enable ? resampleinterpolation_linear
                                           : resampleinterpolation_none);
    }
    bool playRaw(int16_t *array, uint32_t length, uint16_t numChannels) {
        AudioNoInterrupts();
        bool r = reader.playRaw(array, length, numChannels);
        AudioInterrupts();
        return r;
    }
    void setPlaybackRate(double f) { reader.setPlaybackRate(f); }
    void setLoopType(newdigate::loop_type t) { reader.setLoopType(t); }
    void stop() { AudioNoInterrupts(); reader.stop(); AudioInterrupts(); }
    bool isPlaying() { return reader.isPlaying(); }
    uint32_t positionMillis() { return reader.positionMillis(); }
    uint32_t lengthMillis() { return reader.lengthMillis(); }

    void update(void) override {
        if (!reader.isPlaying()) return;
        audio_block_t *b = allocate();
        if (!b) return;
        int16_t *chans[1] = { b->data };
        unsigned got = reader.read((void **)chans, AUDIO_BLOCK_SAMPLES);
        if (got == 0) { release(b); return; }
        if (got < (unsigned)AUDIO_BLOCK_SAMPLES)
            std::memset(b->data + got, 0, (AUDIO_BLOCK_SAMPLES - got) * sizeof(int16_t));
        transmit(b, 0);
        release(b);
    }

private:
    ArrayResamplingReader reader;
};

#endif
