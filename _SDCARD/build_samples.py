#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the ichosynth / TŒRN factory sample set on the micro SD.

Downloads public-domain drum-machine one-shots from the `drum_sklad` collection
(https://github.com/psemiletov/drum_sklad — "free and unencumbered samples
released into the public domain"), converts every file to the exact format the
TŒRN firmware loads (WAV PCM, MONO, 16-bit, 44100 Hz, 44-byte header) and lays
them out the way the firmware expects:

  Samplepacks (loaded whole at boot / via the pack selector):
     <pack>/1.wav .. <pack>/8.wav      one file per voice channel (1..8)
     pack 0 = factory default kit (so a fresh unit boots with sound)
     packs 1..5 = extra kits

  Sample browser (SET_WAV, free WAV files, up to 999):
     samples/<category>/<name>.wav

No external tools needed (no ffmpeg): the WAV reader/converter below is pure
Python (handles PCM 8/16/24/32-bit, IEEE float, WAVE_FORMAT_EXTENSIBLE, any
channel count and sample rate).

Run:  python _SDCARD/build_samples.py
      python _SDCARD/build_samples.py --no-clean    # keep old _N.wav files
"""
import io
import os
import struct
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/psemiletov/drum_sklad/main/"
DST_RATE = 44100

# ---------------------------------------------------------------------------
# Sample map.  Each pack = 8 voices: KICK / SNARE / CL-HAT / OP-HAT / CLAP /
# TOM / PERC / PERC.  Source paths are relative to the drum_sklad repo root.
# ---------------------------------------------------------------------------
PACKS = {
    # pack 0 == pack 1 (808): pack 0 is the factory default so a virgin unit
    # boots with audible sound regardless of the stored pack id.
    0: ("808 (ASR-X)", [
        "ASR-X Pro/808Kick.wav", "ASR-X Pro/808Snare.wav",
        "ASR-X Pro/808HatClose.wav", "ASR-X Pro/808HatOpen.wav",
        "ASR-X Pro/808Clap.wav", "ASR-X Pro/808Tom.wav",
        "ASR-X Pro/808Cowbell.wav", "ASR-X Pro/808Clave.wav"]),
    1: ("808 (ASR-X)", [
        "ASR-X Pro/808Kick.wav", "ASR-X Pro/808Snare.wav",
        "ASR-X Pro/808HatClose.wav", "ASR-X Pro/808HatOpen.wav",
        "ASR-X Pro/808Clap.wav", "ASR-X Pro/808Tom.wav",
        "ASR-X Pro/808Cowbell.wav", "ASR-X Pro/808Clave.wav"]),
    2: ("Drumulator (E-mu)", [
        "Drumulator/bass.wav", "Drumulator/snare.wav",
        "Drumulator/hihat-closed.wav", "Drumulator/hihat-open.wav",
        "Drumulator/clap.wav", "Drumulator/lo-tom.wav",
        "Drumulator/rim.wav", "Drumulator/cowbell.wav"]),
    3: ("Cheetah SpecDrum", [
        "Cheetah SpecDrum Standard/kick.wav", "Cheetah SpecDrum Standard/snare.wav",
        "Cheetah SpecDrum Standard/hihat_c.wav", "Cheetah SpecDrum Standard/hihat_o.wav",
        "Cheetah SpecDrum Standard/clap.wav", "Cheetah SpecDrum Standard/tom_low.wav",
        "Cheetah SpecDrum Standard/tom_mid.wav", "Cheetah SpecDrum Standard/cowbell.wav"]),
    4: ("Technics DP50", [
        "Technics PCM DP50/bd.wav", "Technics PCM DP50/snare.wav",
        "Technics PCM DP50/hihat_closed.wav", "Technics PCM DP50/hihat_open.wav",
        "Technics PCM DP50/clap.wav", "Technics PCM DP50/tom1.wav",
        "Technics PCM DP50/rim.wav", "Technics PCM DP50/ride.wav"]),
    5: ("Rokton UDS / Lel (Soviet)", [
        "Rokton UDS/bd.wav", "Rokton UDS/sd.wav",
        "Rokton UDS/hi hat.wav", "Rokton UDS/cymbal.wav",
        "Lel-DR8/rimshot.wav", "Rokton UDS/hi tom.wav",  # Rokton clap source is degenerate (11ms)
        "Rokton UDS/mid tom.wav", "Rokton UDS/low tom.wav"]),
}

# Browser library: samples/<category>/<dest-name>.wav  ->  source path
BROWSER = {
    "kick": {
        "drumulator-bass": "Drumulator/bass.wav",
        "cheetah-electro": "Cheetah SpecDrum Electro/kick.wav",
        "technics-bd": "Technics PCM DP50/bd.wav",
        "soundmaster-sr88": "SoundMaster SR-88/kick.wav",
        "rokton-bd": "Rokton UDS/bd.wav",
        "mti-ao1": "MTI AO-1/kick.wav",
    },
    "snare": {
        "drumulator": "Drumulator/snare.wav",
        "cheetah": "Cheetah SpecDrum Standard/snare.wav",
        "technics": "Technics PCM DP50/snare.wav",
        "soundmaster-long": "SoundMaster SR-88/snare_long.wav",
        "fricke-mfb": "Fricke MFB512/mfb_snare.wav",
        "rokton-sd": "Rokton UDS/sd.wav",
    },
    "hat": {
        "cheetah-closed": "Cheetah SpecDrum Standard/hihat_c.wav",
        "cheetah-open": "Cheetah SpecDrum Standard/hihat_o.wav",
        "drumulator-closed": "Drumulator/hihat-closed.wav",
        "drumulator-open": "Drumulator/hihat-open.wav",
        "fricke-closed": "Fricke MFB512/mfb_cl_hat.wav",
        "fricke-open": "Fricke MFB512/mfb_op_hat.wav",
    },
    "clap": {
        "drumulator": "Drumulator/clap.wav",
        "cheetah": "Cheetah SpecDrum Standard/clap.wav",
        "technics": "Technics PCM DP50/clap.wav",
        "fricke-mfb": "Fricke MFB512/mfb_clap.wav",
        "wooden": "Wooden/clap.wav",
    },
    "tom": {
        "drumulator-hi": "Drumulator/hi-tom.wav",
        "drumulator-mid": "Drumulator/mid-tom.wav",
        "drumulator-lo": "Drumulator/lo-tom.wav",
        "cheetah-low": "Cheetah SpecDrum Standard/tom_low.wav",
        "technics-1": "Technics PCM DP50/tom1.wav",
    },
    "perc": {
        "drumulator-cowbell": "Drumulator/cowbell.wav",
        "drumulator-clave": "Drumulator/clave.wav",
        "drumulator-rim": "Drumulator/rim.wav",
        "mti-bongo": "MTI AO-1/bongo.wav",
        "mti-conga": "MTI AO-1/conga.wav",
        "technics-tamb": "Technics PCM DP50/tamb.wav",
        "lel-stick": "Lel-DR8/stick.wav",
    },
    "fx": {
        "wooden-knock": "Wooden/knock.wav",
        "wooden-tyk": "Wooden/tyk.wav",
        "wooden-hit": "Wooden/hit-short.wav",
        "wooden-crumble": "Wooden/crumble.wav",
        "lel-guitar": "Lel-DR8/guitar.wav",
    },
}


# ---------------------------------------------------------------------------
# WAV decode (robust) -> mono float list ; encode -> mono/16-bit/44100 WAV
# ---------------------------------------------------------------------------
def _iter_chunks(b):
    pos = 12
    n = len(b)
    while pos + 8 <= n:
        cid = b[pos:pos + 4]
        size = struct.unpack("<I", b[pos + 4:pos + 8])[0]
        body = b[pos + 8:pos + 8 + size]
        yield cid, body
        pos += 8 + size + (size & 1)  # chunks are word-aligned


def decode_wav(b):
    """Return (rate, mono_floats) from arbitrary PCM/float WAV bytes."""
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    fmt = None
    data = None
    for cid, body in _iter_chunks(b):
        if cid == b"fmt ":
            tag, ch, rate, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:           # WAVE_FORMAT_EXTENSIBLE
                tag = struct.unpack("<H", body[24:26])[0]   # real format from GUID
            fmt = (tag, ch, rate, bits)
        elif cid == b"data":
            data = body
    if not fmt or data is None:
        raise ValueError("missing fmt/data chunk")
    tag, ch, rate, bits = fmt
    nbytes = bits // 8
    frame = nbytes * ch
    if frame == 0:
        raise ValueError("bad fmt")
    nframes = len(data) // frame

    # --- per-sample reader -> float in [-1, 1] ---
    if tag == 3:  # IEEE float
        if bits == 32:
            rd = lambda o: struct.unpack_from("<f", data, o)[0]
        elif bits == 64:
            rd = lambda o: struct.unpack_from("<d", data, o)[0]
        else:
            raise ValueError("float bits %d" % bits)
    elif tag == 1:  # PCM int
        if bits == 8:   # unsigned
            rd = lambda o: (data[o] - 128) / 128.0
        elif bits == 16:
            rd = lambda o: struct.unpack_from("<h", data, o)[0] / 32768.0
        elif bits == 24:
            def rd(o):
                v = data[o] | (data[o + 1] << 8) | (data[o + 2] << 16)
                if v & 0x800000:
                    v -= 0x1000000
                return v / 8388608.0
        elif bits == 32:
            rd = lambda o: struct.unpack_from("<i", data, o)[0] / 2147483648.0
        else:
            raise ValueError("pcm bits %d" % bits)
    else:
        raise ValueError("format tag %d" % tag)

    mono = [0.0] * nframes
    inv = 1.0 / ch
    for i in range(nframes):
        base = i * frame
        acc = 0.0
        for c in range(ch):
            acc += rd(base + c * nbytes)
        mono[i] = acc * inv
    return rate, mono


def resample(mono, src_rate, dst_rate):
    if src_rate == dst_rate or not mono:
        return mono
    ratio = dst_rate / src_rate
    out_n = max(1, int(round(len(mono) * ratio)))
    out = [0.0] * out_n
    step = src_rate / dst_rate
    pos = 0.0
    last = len(mono) - 1
    for i in range(out_n):
        idx = int(pos)
        if idx >= last:
            out[i] = mono[last]
        else:
            frac = pos - idx
            out[i] = mono[idx] * (1.0 - frac) + mono[idx + 1] * frac
        pos += step
    return out


def encode_wav_mono16(mono):
    pcm = bytearray(len(mono) * 2)
    for i, v in enumerate(mono):
        if v > 1.0:
            v = 1.0
        elif v < -1.0:
            v = -1.0
        struct.pack_into("<h", pcm, i * 2, int(round(v * 32767.0)))
    data_bytes = len(pcm)
    out = io.BytesIO()
    out.write(b"RIFF")
    out.write(struct.pack("<I", 36 + data_bytes))
    out.write(b"WAVE")
    out.write(b"fmt ")
    out.write(struct.pack("<IHHIIHH", 16, 1, 1, DST_RATE, DST_RATE * 2, 2, 16))
    out.write(b"data")
    out.write(struct.pack("<I", data_bytes))
    out.write(pcm)
    return out.getvalue()


# ---------------------------------------------------------------------------
def fetch(rel_path, tries=3):
    url = RAW + urllib.parse.quote(rel_path)
    last = None
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ichosynth-build"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (t + 1))
    raise RuntimeError("download failed: %s (%s)" % (rel_path, last))


def convert(raw_bytes):
    rate, mono = decode_wav(raw_bytes)
    mono = resample(mono, rate, DST_RATE)
    return encode_wav_mono16(mono)


def write_out(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def clean_legacy():
    """Remove old NI404-style _<n>.wav files (not loaded by TŒRN firmware)."""
    removed = 0
    for root, _dirs, files in os.walk(HERE):
        for fn in files:
            base = fn.lower()
            if base.startswith("_") and base.endswith(".wav") and base[1:-4].isdigit():
                os.remove(os.path.join(root, fn))
                removed += 1
    if removed:
        print("removed %d legacy _N.wav files" % removed)


def main():
    clean = "--no-clean" not in sys.argv
    if clean:
        clean_legacy()

    cache = {}

    def get(rel):
        if rel not in cache:
            cache[rel] = convert(fetch(rel))
        return cache[rel]

    print("== samplepacks ==")
    for pack, (name, files) in sorted(PACKS.items()):
        print("pack %d  (%s)" % (pack, name))
        for ch, rel in enumerate(files, start=1):
            data = get(rel)
            out = os.path.join(HERE, str(pack), "%d.wav" % ch)
            write_out(out, data)
            print("   %d.wav  <- %s  (%d KB)" % (ch, rel, len(data) // 1024))

    print("\n== browser library (samples/) ==")
    for cat, items in BROWSER.items():
        for name, rel in items.items():
            data = get(rel)
            out = os.path.join(HERE, "samples", cat, name + ".wav")
            write_out(out, data)
            print("   samples/%s/%s.wav  <- %s" % (cat, name, rel))

    n = len(cache)
    print("\nDone. %d unique sources converted to mono/16-bit/44100 WAV." % n)


if __name__ == "__main__":
    main()
