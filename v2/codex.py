#!/usr/bin/env python3

import struct

from codex37 import decode37

# DECODE

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
            out[dst:dst + w] = f[src:src + w]
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

decoders = {
    21: unidecoder,
    44: unidecoder,
    47: decode47,
    37: decode37
}

def get_decoder(codec):
    if codec in decoders:
        return decoders[codec]
    return NotImplemented

def to_matrix(w, h, data):
    return [data[i*w:(i+1)*w] for i in range(h)]

# ENCODE

def codec44(width, height, out):
    BG = 39

    f = b''
    for line in out:
        l = b''
        done = 0
        while done < width:
            i = 0
            while done + i < width and line[done+i] == BG:
                i += 1
            off = i
            while done + i < width and line[done+i] != BG:
                i += 1
            lst = line[done+off:done+i]
            l += struct.pack('<H', off)
            r = 1 if (done + i < width) else 0
            if len(lst) > 0:
                l += struct.pack('<H', len(lst) - r)
                for it in lst:
                    l += struct.pack('<B', it)
            else:
                l += struct.pack('<H', 0)
            done += i
        f += struct.pack('<H', len(l) + 1) + l + struct.pack('<B', 0)
    f += struct.pack('<H', width + 5) + b'\x00\x00' + struct.pack('<H', width)
    for i in range(width):
        f += b'\x00'
    if len(f) % 2 == 0:
        f += b'\x00\x00'
    return f

def codec21(width, height, out):
    BG = 39

    f = b''
    for line in (out + [[BG for _ in range(width)]]):
        l = b''
        done = 0
        while done <= width:
            i = 0
            while done + i < width and line[done+i] == BG:
                i += 1
            off = i
            r = i + 1
            if done + r > width:
                l += (struct.pack('<H', r))
                break
            while done + i < width and line[done+i] != BG:
                i += 1
            lst = line[done+off:done+i]
            l += struct.pack('<H', off)
            if len(lst) > 0:
                l += struct.pack('<H', len(lst) - 1)
                for it in lst:
                    l += struct.pack('<B', it)
            done += i
        f += struct.pack('<H', len(l)) + l
    return f

encoders = {
    21: codec21,
    44: codec44
}

def get_encoder(codec):
    if codec in encoders:
        return encoders[codec]
    return NotImplemented
