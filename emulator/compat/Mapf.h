// Mapf.h — desktop shim for the Arduino "Mapf" library used by the firmware.
// Provides mapf(): a floating-point version of Arduino's integer map().
#ifndef NI404_COMPAT_MAPF_H
#define NI404_COMPAT_MAPF_H

inline float mapf(float x, float in_min, float in_max, float out_min, float out_max) {
    if (in_max == in_min) return out_min;
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

#endif // NI404_COMPAT_MAPF_H
