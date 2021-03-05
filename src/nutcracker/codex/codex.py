#!/usr/bin/env python3
import struct

from .codex37_np import decode37 as e_decode37, fake_encode37
from .codex47_np import decode47 as e_decode47, fake_encode47
from .codex1 import read_le_uint16, to_matrix, encode1, decode1

# from codex37_old import decode37

# DECODE

encode1 = encode1


def unidecoder(width, height, f):
    BG = 39

    out = [BG for _ in range(width * height)]
    dst = 0
    src = 0
    for _ in range(height):
        dstPtrNext = dst + width
        srcPtrNext = src + 2 + read_le_uint16(f[src:])
        src += 2
        lens = width
        while lens > 0:
            offs = read_le_uint16(f[src:])
            src += 2
            dst += offs
            lens -= offs
            w = read_le_uint16(f[src:]) + 1
            src += 2
            lens -= w
            if lens < 0:
                w += lens
            out[dst : dst + w] = f[src : src + w]
            dst += w
            src += w
        assert dst == dstPtrNext
        dst = dstPtrNext
        src = srcPtrNext
    if src != len(f):
        print('DIFF', f[src:])
    return to_matrix(width, height, out)


def decode47(width, height, f):
    return e_decode47(f, width, height)


def decode37(width, height, f):
    return e_decode37(f, width, height)


def unidecoder_factory(width, height):
    return unidecoder


decoders = {
    1: decode1,
    21: unidecoder,
    44: unidecoder,
    47: decode47,
    37: decode37,
}


def get_decoder(codec):
    if codec in decoders:
        return decoders[codec]
    return NotImplemented


# ENCODE

def codec44(width, height, out):
    BG = 39

    f = b''
    for line in out:
        le = b''
        done = 0
        while done < width:
            i = 0
            while done + i < width and line[done + i] == BG:
                i += 1
            off = i
            while done + i < width and line[done + i] != BG:
                i += 1
            lst = line[done + off : done + i]
            le += struct.pack('<H', off)
            r = 1 if (done + i < width) else 0
            if len(lst) > 0:
                le += struct.pack('<H', len(lst) - r)
                for it in lst:
                    le += struct.pack('<B', it)
            else:
                le += struct.pack('<H', 0)
            done += i
        f += struct.pack('<H', len(le) + 1) + le + struct.pack('<B', 0)
    f += struct.pack('<H', width + 5) + b'\x00\x00' + struct.pack('<H', width)
    f += b'\x00' * (width + 1)
    if len(f) % 2 != 0:
        f += b'\x00'
    return f


def codec21(width, height, out):
    BG = 39

    f = b''
    for line in out + [[BG for _ in range(width)]]:
        le = b''
        done = 0
        while done <= width:
            i = 0
            while done + i < width and line[done + i] == BG:
                i += 1
            off = i
            r = i + 1
            if done + r > width:
                le += struct.pack('<H', r)
                break
            while done + i < width and line[done + i] != BG:
                i += 1
            lst = line[done + off : done + i]
            le += struct.pack('<H', off)
            if len(lst) > 0:
                le += struct.pack('<H', len(lst) - 1)
                for it in lst:
                    le += struct.pack('<B', it)
            done += i
        f += struct.pack('<H', len(le)) + le
    if len(f) % 2 != 0:
        f += b'\x00'
    return f


encoders = {
    21: codec21,
    44: codec44,
    37: fake_encode37,
    47: fake_encode47,
}


def get_encoder(codec):
    if codec in encoders:
        return encoders[codec]
    print(codec)
    return NotImplemented
