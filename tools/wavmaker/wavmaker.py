#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ichosynth / TŒRN — WAV Maker (CLI)

Converts WAV files into the exact format the TŒRN firmware loads —
MONO / 16-bit / 44100 Hz — and lays them out the way the firmware reads them.

The firmware has TWO sample systems:

  * Samplepack:  <pack>/1.wav .. <pack>/8.wav   (8 voices, loaded as a set)
  * Browser:     samples/<folder>/<name>.wav    (free files, browsed in SET_WAV)

Usage:
  python wavmaker.py                 convert every WAV in THIS folder in place
                                     (mono/16/44100), keeping the file names
  python wavmaker.py <dir>           same, for <dir>
  python wavmaker.py --pack N <dir>  build samplepack N: take the WAVs in <dir>
                                     (sorted), convert, write N/1.wav .. N/8.wav
                                     (max 8 files)

No external tools and no `audioop` needed: the converter below is pure Python
(handles PCM 8/16/24/32-bit, IEEE float and WAVE_FORMAT_EXTENSIBLE, any channel
count and sample rate).
"""
import array
import math
import operator
import os
import struct
import sys

TARGET_RATE = 44100


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


def convert_file(src, dst):
    with open(src, "rb") as f:
        out = convert_bytes(f.read())
    tmp = dst + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(out)
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# --------------------------------------------------------------------------
def wavs_in(directory):
    return [f for f in sorted(os.listdir(directory)) if f.lower().endswith(".wav")]


def convert_in_place(directory):
    n = 0
    for fn in wavs_in(directory):
        p = os.path.join(directory, fn)
        try:
            convert_file(p, p)
            print(f"  {fn}  -> mono/16/44100")
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ! skipped {fn}: {e}")
    return n


def build_pack(pack, directory):
    files = wavs_in(directory)
    # ignore files already named 1..8.wav so re-running is idempotent
    files = [f for f in files if not (f[:-4].isdigit() and 1 <= int(f[:-4]) <= 8)]
    if not files:
        print("No source WAVs to build the pack from.")
        return 0
    if len(files) > 8:
        print(f"  ! {len(files)} files found; only the first 8 become voices 1..8.")
        files = files[:8]
    dst_dir = os.path.join(directory, str(pack))
    os.makedirs(dst_dir, exist_ok=True)
    n = 0
    for i, fn in enumerate(files, start=1):
        dst = os.path.join(dst_dir, f"{i}.wav")
        try:
            convert_file(os.path.join(directory, fn), dst)
            print(f"  voce {i}: {fn}  -> {pack}/{i}.wav")
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ! voce {i} skipped {fn}: {e}")
    return n


USAGE = "uso: python wavmaker.py [<cartella>] | --pack N <cartella>   (N = 0-99)"


def main(argv):
    """Return the process exit code (0 ok, 1 some files failed, 2 bad usage)."""
    pack = None
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--pack":
            i += 1
            val = argv[i] if i < len(argv) else ""
            if not val.isdigit() or not (0 <= int(val) <= 99):
                print(f"Errore: --pack vuole un numero tra 0 e 99 (ricevuto: {val or 'niente'}).",
                      file=sys.stderr)
                print(USAGE, file=sys.stderr)
                return 2
            pack = int(val)
        elif a in ("-h", "--help"):
            print(USAGE)
            return 0
        else:
            args.append(a)
        i += 1
    if len(args) > 1:
        print("Errore: una sola cartella alla volta.", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    # senza argomenti: la cartella sdcard/ del repo (lo script sta in tools/wavmaker/)
    directory = args[0] if args else os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "sdcard"))
    if not os.path.isdir(directory):
        print(f"Errore: cartella non trovata: {directory}", file=sys.stderr)
        return 2

    print("ichosynth / TŒRN — WAV Maker (CLI)")
    print("Formato di destinazione: WAV mono / 16-bit / 44100 Hz")
    print(f"Cartella: {directory}\n")

    if pack is not None:
        print(f"Costruisco il samplepack {pack} ({pack}/1.wav .. {pack}/8.wav):")
        n = build_pack(pack, directory)
        total = min(8, len([f for f in wavs_in(directory)
                            if not (f[:-4].isdigit() and 1 <= int(f[:-4]) <= 8)]))
    else:
        print("Converto i WAV in questa cartella (nomi invariati):")
        total = len(wavs_in(directory))
        n = convert_in_place(directory)
    print(f"\nFatto: {n} file.")
    return 0 if n == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
