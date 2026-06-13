// loop_type.h — newdigate teensy-variable-playback enums (reconstructed to match
// the ResamplingReader.h interface in ../_DOCS).
#ifndef NI404_NEWDIGATE_LOOP_TYPE_H
#define NI404_NEWDIGATE_LOOP_TYPE_H

namespace newdigate {
enum loop_type {
    looptype_none,
    looptype_repeat,
    looptype_pingpong
};
enum play_start {
    play_start_sample,
    play_start_loop
};
}

// ResamplingReader.h refers to these unscoped (e.g. looptype_repeat,
// play_start::play_start_sample) inside namespace newdigate.
using newdigate::looptype_none;
using newdigate::looptype_repeat;
using newdigate::looptype_pingpong;
using newdigate::play_start;
using newdigate::loop_type;

#endif
