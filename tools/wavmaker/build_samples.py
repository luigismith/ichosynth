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

  Sample browser (SET_WAV, free WAV files, max 256 per folder, names <= 60 chars):
     samples/<category>/<name>.wav

No external tools needed (no ffmpeg): the WAV reader/converter below is pure
Python (handles PCM 8/16/24/32-bit, IEEE float, WAVE_FORMAT_EXTENSIBLE, any
channel count and sample rate).

Run:  python tools/wavmaker/build_samples.py
      python tools/wavmaker/build_samples.py --no-clean    # keep old _N.wav files
"""
import array
import math
import operator
import os
import struct
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SD = os.path.normpath(os.path.join(HERE, "..", "..", "sdcard"))   # contenuto della SD nel repo
RAW = "https://raw.githubusercontent.com/psemiletov/drum_sklad/main/"
TARGET_RATE = DST_RATE = 44100

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


# --------------------------------------------------------------------------
# pure-python WAV codec  (mono / 16-bit / 44100 Hz output)
# NB: the same block lives in wavmaker.py, wavmaker_gui.py and build_samples.py
#     (each script stays standalone) — keep the three copies identical.
# --------------------------------------------------------------------------
def _iter_chunks(b):
    pos, n = 12, len(b)
    while pos + 8 <= n:
        cid = b[pos:pos + 4]
        size = struct.unpack("<I", b[pos + 4:pos + 8])[0]
        yield cid, b[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)          # chunks are word-aligned


def wav_info(b):
    """RIFF/WAVE bytes -> (tag, channels, rate, bits, data_bytes). Raises ValueError."""
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    fmt = data = None
    for cid, body in _iter_chunks(b):
        if cid == b"fmt ":
            if len(body) < 16:
                raise ValueError("fmt chunk troppo corto")
            tag, ch, rate, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:    # WAVE_FORMAT_EXTENSIBLE
                tag = struct.unpack("<H", body[24:26])[0]   # real format from GUID
            fmt = (tag, ch, rate, bits)
        elif cid == b"data":
            data = body
    if not fmt or data is None:
        raise ValueError("missing fmt/data chunk")
    tag, ch, rate, bits = fmt
    if ch == 0 or rate == 0 or bits == 0 or bits % 8:
        raise ValueError("bad fmt (ch=%d rate=%d bits=%d)" % (ch, rate, bits))
    return tag, ch, rate, bits, data


def _samples(data, tag, bits):
    """Interleaved sample bytes -> list of floats in -1..1 (all channels)."""
    if tag == 1 and bits == 8:                 # unsigned 8-bit
        return [(v - 128) / 128.0 for v in data]
    if tag == 1 and bits == 24:
        n = len(data) // 3
        out = [0.0] * n
        for i in range(n):
            o = i * 3
            v = data[o] | (data[o + 1] << 8) | (data[o + 2] << 16)
            out[i] = (v - 0x1000000 if v & 0x800000 else v) / 8388608.0
        return out
    if tag == 1 and bits in (16, 32):
        code = "h" if bits == 16 else ("i" if array.array("i").itemsize == 4 else "l")
        scale = 1.0 / (32768.0 if bits == 16 else 2147483648.0)
    elif tag == 3 and bits in (32, 64):        # IEEE float
        code = "f" if bits == 32 else "d"
        scale = 1.0
    elif tag in (1, 3):
        raise ValueError("%s bits %d" % ("pcm" if tag == 1 else "float", bits))
    else:
        raise ValueError("format tag %d" % tag)
    a = array.array(code)
    a.frombytes(data[:len(data) - len(data) % a.itemsize])
    if sys.byteorder != "little":
        a.byteswap()
    if scale == 1.0:
        return [v if v == v else 0.0 for v in a]      # NaN -> 0
    return [v * scale for v in a]


def decode_wav(b):
    """Arbitrary PCM/float WAV bytes -> (rate, [mono floats in -1..1])."""
    tag, ch, rate, bits, data = wav_info(b)
    s = _samples(data, tag, bits)
    if ch == 1:
        return rate, s
    nframes = len(s) // ch
    inv = 1.0 / ch
    cols = [s[c:nframes * ch:ch] for c in range(ch)]
    return rate, [sum(fr) * inv for fr in zip(*cols)]


# band-limited resampler: polyphase windowed-sinc (Kaiser), low-pass at
# 0.45 * min(fs_in, fs_out) so nothing above the new Nyquist folds back.
_RS_CUT = 0.45          # cutoff, fraction of the lower sample rate
_RS_ZEROS = 24          # sinc zero-crossings per side
_RS_BETA = 8.6          # Kaiser beta (~-85 dB stopband)
_RS_MAX_PHASES = 1024   # odd rate ratios: phase quantised to 1/1024 sample


def _bessel_i0(x):
    s = term = 1.0
    y = x * x / 4.0
    k = 1
    while term > 1e-12 * s:
        term *= y / (k * k)
        s += term
        k += 1
    return s


def resample(mono, src_rate, dst_rate):
    if src_rate == dst_rate or not mono:
        return mono
    g = math.gcd(int(src_rate), int(dst_rate))
    up, down = int(dst_rate) // g, int(src_rate) // g
    out_n = max(1, int(round(len(mono) * dst_rate / src_rate)))
    fc = _RS_CUT * min(src_rate, dst_rate) / src_rate      # cycles / input sample
    half = _RS_ZEROS / (2.0 * fc)                           # kernel half-width
    taps = int(math.ceil(half))
    width = 2 * taps
    i0b = _bessel_i0(_RS_BETA)
    nph = up if up <= _RS_MAX_PHASES else _RS_MAX_PHASES
    cache = {}

    def kernel(q):
        frac = q / nph
        c = []
        for j in range(-taps + 1, taps + 1):
            d = frac - j                     # distance input sample -> output point
            u = d / half
            if abs(u) >= 1.0:
                c.append(0.0)
                continue
            x = 2.0 * fc * d
            sinc = 1.0 if x == 0.0 else math.sin(math.pi * x) / (math.pi * x)
            c.append(2.0 * fc * sinc * _bessel_i0(_RS_BETA * math.sqrt(1.0 - u * u)) / i0b)
        tot = sum(c)
        return [v / tot for v in c]           # unity gain at DC for every phase

    xp = [0.0] * taps + list(mono) + [0.0] * (taps + 2)
    out = [0.0] * out_n
    mul = operator.mul
    for n in range(out_n):
        k, r = divmod(n * down, up)
        if nph == up:
            q = r
        else:
            q = int(round(r * nph / up))
            if q == nph:
                k, q = k + 1, 0
        c = cache.get(q)
        if c is None:
            c = cache[q] = kernel(q)
        out[n] = sum(map(mul, c, xp[k + 1:k + 1 + width]))
    return out


def _wav_header(nbytes):
    return (b"RIFF" + struct.pack("<I", 36 + nbytes) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, TARGET_RATE, TARGET_RATE * 2, 2, 16)
            + b"data" + struct.pack("<I", nbytes))


def encode_wav_mono16(mono):
    # symmetric scaling (decode /32768, encode *32768 clipped to int16): a 16-bit
    # source survives decode -> encode bit-exact, so re-converting is lossless
    pcm = array.array("h", [0]) * len(mono)
    for i, v in enumerate(mono):
        x = v * 32768.0
        if x >= 32767.0:
            pcm[i] = 32767
        elif x <= -32768.0:
            pcm[i] = -32768
        elif x == x:                           # NaN -> 0
            pcm[i] = int(round(x))
    if sys.byteorder != "little":
        pcm.byteswap()
    raw = pcm.tobytes()
    return _wav_header(len(raw)) + raw


def convert_bytes(raw):
    """Any WAV -> mono/16-bit/44100 WAV bytes (44-byte header)."""
    tag, ch, rate, bits, data = wav_info(raw)
    if tag == 1 and ch == 1 and bits == 16 and rate == TARGET_RATE:
        pcm = bytes(data[:len(data) & ~1])     # already the target: samples untouched
        return _wav_header(len(pcm)) + pcm
    rate, mono = decode_wav(raw)
    return encode_wav_mono16(resample(mono, rate, TARGET_RATE))


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
    return convert_bytes(raw_bytes)


def write_out(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def clean_legacy():
    """Remove old NI404-style _<n>.wav files (not loaded by TŒRN firmware)."""
    removed = 0
    for root, _dirs, files in os.walk(SD):
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
            out = os.path.join(SD, str(pack), "%d.wav" % ch)
            write_out(out, data)
            print("   %d.wav  <- %s  (%d KB)" % (ch, rel, len(data) // 1024))

    print("\n== browser library (samples/) ==")
    for cat, items in BROWSER.items():
        for name, rel in items.items():
            data = get(rel)
            out = os.path.join(SD, "samples", cat, name + ".wav")
            write_out(out, data)
            print("   samples/%s/%s.wav  <- %s" % (cat, name, rel))

    n = len(cache)
    print("\nDone. %d unique sources converted to mono/16-bit/44100 WAV." % n)


if __name__ == "__main__":
    main()
