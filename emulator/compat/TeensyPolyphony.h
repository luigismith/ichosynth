// TeensyPolyphony.h — desktop port of the newdigate teensy-polyphony API used by
// the NI404 firmware. Each `arraysampler` owns ONE resampling voice (an
// AudioPlayArrayResmp already patched into the audio graph in audioinit.h via
// its envelope/filter/mixer cords) plus the sample data registered with
// addSample(). noteEvent() triggers playback at the right pitch and gates the
// envelope.
//
// Pitch model: playbackRate = 2^((note - rootNote)/12), rootNote from
// addSample(rootNote, ...). This is the standard newdigate semitone mapping;
// the firmware's own note arithmetic feeds `note`, so behavior tracks the device.
#ifndef NI404_COMPAT_TEENSYPOLYPHONY_H
#define NI404_COMPAT_TEENSYPOLYPHONY_H

#include "Audio.h"
#include "newdigate/audio_play_array_resmp.h"
#include <cmath>

class arraysampler {
public:
    arraysampler() {}

    void addVoice(AudioPlayArrayResmp &snd, AudioMixer4 &mix, int port, AudioEffectEnvelope &env) {
        _snd = &snd; _mix = &mix; _port = port; _env = &env;
    }

    // Register the sample this sampler plays. `rootNote` is the note at which the
    // sample plays back at its native rate.
    void addSample(int rootNote, int16_t *data, int length, int numChannels) {
        _rootNote = rootNote; _data = data; _length = length; _channels = numChannels;
    }

    // Drop the registered sample and silence the voice (firmware calls this
    // before (re)loading a sample into a channel).
    void removeAllSamples() {
        AudioNoInterrupts();
        if (_snd) _snd->stop();
        _data = nullptr; _length = 0;
        AudioInterrupts();
    }

    // note  : requested note number (pitch)
    // velocity: 1..127
    // on    : true=note-on, false=note-off
    // (4th flag from the firmware is a retrigger/legato hint — not needed here)
    void noteEvent(int note, int velocity, bool on, bool /*flag*/) {
        AudioNoInterrupts();
        if (on) {
            if (_snd && _data && _length > 0) {
                double rate = std::pow(2.0, (double)(note - _rootNote) / 12.0);
                _snd->playRaw(_data, (uint32_t)_length, (uint16_t)_channels);
                _snd->setPlaybackRate(rate);
            }
            if (_mix && _port >= 0) {
                float g = velocity / 127.0f;
                if (g < 0) g = 0; else if (g > 1) g = 1;
                _mix->gain(_port, g);
            }
            if (_env) _env->noteOn();
        } else {
            if (_env) _env->noteOff();
        }
        AudioInterrupts();
    }

    bool isPlaying() { return _snd ? _snd->isPlaying() : false; }

private:
    AudioPlayArrayResmp *_snd = nullptr;
    AudioMixer4 *_mix = nullptr;
    AudioEffectEnvelope *_env = nullptr;
    int _port = -1;
    int _rootNote = 36;
    int16_t *_data = nullptr;
    int _length = 0;
    int _channels = 1;
};

#endif // NI404_COMPAT_TEENSYPOLYPHONY_H
