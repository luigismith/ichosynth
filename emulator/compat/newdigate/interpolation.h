// interpolation.h — newdigate teensy-variable-playback interpolation support
// (reconstructed to satisfy ResamplingReader.h).
#ifndef NI404_NEWDIGATE_INTERPOLATION_H
#define NI404_NEWDIGATE_INTERPOLATION_H

#include <cstdint>

enum ResampleInterpolationType {
    resampleinterpolation_none,
    resampleinterpolation_linear,
    resampleinterpolation_quadratic
};

struct InterpolationData {
    double y = 0.0;
};

// 4-point cubic (Catmull-Rom-style) interpolation. x in [1,2] selects between
// p1 and p2 with p0/p3 as the surrounding points (matches the library's usage
// `fastinterpolate(p0,p1,p2,p3, 1.0+frac)`).
inline int16_t fastinterpolate(int p0, int p1, int p2, int p3, double x) {
    double t = x - 1.0;  // 0..1 between p1 and p2
    double a0 = p3 - p2 - p0 + p1;
    double a1 = p0 - p1 - a0;
    double a2 = p2 - p0;
    double a3 = p1;
    double v = a0 * t * t * t + a1 * t * t + a2 * t + a3;
    if (v > 32767.0) v = 32767.0;
    if (v < -32768.0) v = -32768.0;
    return (int16_t)v;
}

#endif
