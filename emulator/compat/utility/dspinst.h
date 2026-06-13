// utility/dspinst.h — Teensy CMSIS DSP intrinsics header. The vendored freeverb
// includes it but, on the portable (non-ARM) path, uses only its own local
// sat16(); none of the dsp intrinsics are referenced. Provide the common ones
// anyway as portable C in case other vendored nodes need them.
#ifndef NI404_COMPAT_DSPINST_H
#define NI404_COMPAT_DSPINST_H

#include <cstdint>

static inline int32_t signed_multiply_32x16b(int32_t a, uint32_t b) {
    return (int32_t)(((int64_t)a * (int16_t)(b & 0xFFFF)) >> 16);
}
static inline int32_t signed_multiply_32x16t(int32_t a, uint32_t b) {
    return (int32_t)(((int64_t)a * (int16_t)(b >> 16)) >> 16);
}
static inline int32_t signed_saturate_rshift(int32_t val, int bits, int rshift) {
    int32_t out = val >> rshift;
    int32_t max = (1 << (bits - 1)) - 1, min = -(1 << (bits - 1));
    if (out > max) out = max; else if (out < min) out = min;
    return out;
}
static inline int32_t multiply_16tx16t(int32_t a, int32_t b) {
    return ((int16_t)(a >> 16)) * ((int16_t)(b >> 16));
}
static inline int32_t multiply_16bx16b(int32_t a, int32_t b) {
    return ((int16_t)(a & 0xFFFF)) * ((int16_t)(b & 0xFFFF));
}
static inline uint32_t pack_16x16(int32_t a, int32_t b) {
    return ((uint32_t)(a & 0xFFFF) << 16) | (uint32_t)(b & 0xFFFF);
}

#endif
