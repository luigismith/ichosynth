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
import io
import os
import struct
import sys

TARGET_RATE = 44100


# --------------------------------------------------------------------------
# pure-python WAV codec  (mono / 16-bit / 44100 Hz output)
# --------------------------------------------------------------------------
def _iter_chunks(b):
    pos, n = 12, len(b)
    while pos + 8 <= n:
        cid = b[pos:pos + 4]
        size = struct.unpack("<I", b[pos + 4:pos + 8])[0]
        yield cid, b[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)


def decode_wav(b):
    """Arbitrary PCM/float WAV bytes -> (rate, [mono floats in -1..1])."""
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    fmt = data = None
    for cid, body in _iter_chunks(b):
        if cid == b"fmt ":
            tag, ch, rate, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:
                tag = struct.unpack("<H", body[24:26])[0]
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

    if tag == 3:                       # IEEE float
        if bits == 32:
            rd = lambda o: struct.unpack_from("<f", data, o)[0]
        elif bits == 64:
            rd = lambda o: struct.unpack_from("<d", data, o)[0]
        else:
            raise ValueError("float bits %d" % bits)
    elif tag == 1:                     # PCM int
        if bits == 8:
            rd = lambda o: (data[o] - 128) / 128.0
        elif bits == 16:
            rd = lambda o: struct.unpack_from("<h", data, o)[0] / 32768.0
        elif bits == 24:
            def rd(o):
                v = data[o] | (data[o + 1] << 8) | (data[o + 2] << 16)
                return (v - 0x1000000 if v & 0x800000 else v) / 8388608.0
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
    out_n = max(1, int(round(len(mono) * dst_rate / src_rate)))
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
        v = 1.0 if v > 1.0 else (-1.0 if v < -1.0 else v)
        struct.pack_into("<h", pcm, i * 2, int(round(v * 32767.0)))
    db = len(pcm)
    o = io.BytesIO()
    o.write(b"RIFF"); o.write(struct.pack("<I", 36 + db)); o.write(b"WAVE")
    o.write(b"fmt "); o.write(struct.pack("<IHHIIHH", 16, 1, 1, TARGET_RATE, TARGET_RATE * 2, 2, 16))
    o.write(b"data"); o.write(struct.pack("<I", db)); o.write(pcm)
    return o.getvalue()


def convert_bytes(raw):
    rate, mono = decode_wav(raw)
    return encode_wav_mono16(resample(mono, rate, TARGET_RATE))


def convert_file(src, dst):
    with open(src, "rb") as f:
        out = convert_bytes(f.read())
    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, dst)


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


def main(argv):
    pack = None
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--pack":
            i += 1
            pack = int(argv[i])
        else:
            args.append(a)
        i += 1
    directory = args[0] if args else os.path.dirname(os.path.abspath(__file__))

    print("ichosynth / TŒRN — WAV Maker (CLI)")
    print("Formato di destinazione: WAV mono / 16-bit / 44100 Hz")
    print(f"Cartella: {directory}\n")

    if pack is not None:
        if not (0 <= pack <= 99):
            print("Numero pack non valido (0-99).")
            return
        print(f"Costruisco il samplepack {pack} ({pack}/1.wav .. {pack}/8.wav):")
        n = build_pack(pack, directory)
    else:
        print("Converto i WAV in questa cartella (nomi invariati):")
        n = convert_in_place(directory)
    print(f"\nFatto: {n} file.")


if __name__ == "__main__":
    main(sys.argv[1:])
