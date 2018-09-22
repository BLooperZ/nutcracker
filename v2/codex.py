#!/usr/bin/env python3

import struct

def read_le_uint16(f):
    return struct.unpack('<H', f[:2])[0]

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
            for i in range(w):
                out[dst+i] = struct.unpack('<B', f[src + i:src + i + 1])[0]
            dst += w
            src += w
        dst = dstPtrNext
        src = srcPtrNext
    return to_matrix(width, height, out)

def decode47(width, height, f):
    BG = 39

    a = [b for b in f]
    out = [BG for _ in range(width * height)]
    if len(a) == len(out):
        out = a
        print('Yay')
        if None in a:
            print('Ooof')
            return None
        return to_matrix(width, height, out)
    return None

decoders = {
    21: unidecoder,
    44: unidecoder,
    47: decode47
}

def get_decoder(codec):
    if codec in decoders:
        return decoders[codec]
    return NotImplemented

def to_matrix(w, h, data):
    return [data[i*w:(i+1)*w] for i in range(h)]

