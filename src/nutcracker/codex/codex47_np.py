import io
import struct
from enum import Enum
from datetime import datetime

import numpy as np

from nutcracker.utils import funcutils
from . import bomb

glyph4_x = [
  0, 1, 2, 3, 3, 3, 3, 2, 1, 0, 0, 0, 1, 2, 2, 1,
]

glyph4_y = [
  0, 0, 0, 0, 1, 2, 3, 3, 3, 3, 2, 1, 1, 1, 2, 2,
]

glyph8_x = [
  0, 2, 5, 7, 7, 7, 7, 7, 7, 5, 2, 0, 0, 0, 0, 0,
]

glyph8_y = [
  0, 0, 0, 0, 1, 3, 4, 6, 7, 7, 7, 7, 6, 4, 3, 1,
]

motion_vectors = [
    (   0,   0 ), (  -1, -43 ), (   6, -43 ), (  -9, -42 ), (  13, -41 ),
    ( -16, -40 ), (  19, -39 ), ( -23, -36 ), (  26, -34 ), (  -2, -33 ),
    (   4, -33 ), ( -29, -32 ), (  -9, -32 ), (  11, -31 ), ( -16, -29 ),
    (  32, -29 ), (  18, -28 ), ( -34, -26 ), ( -22, -25 ), (  -1, -25 ),
    (   3, -25 ), (  -7, -24 ), (   8, -24 ), (  24, -23 ), (  36, -23 ),
    ( -12, -22 ), (  13, -21 ), ( -38, -20 ), (   0, -20 ), ( -27, -19 ),
    (  -4, -19 ), (   4, -19 ), ( -17, -18 ), (  -8, -17 ), (   8, -17 ),
    (  18, -17 ), (  28, -17 ), (  39, -17 ), ( -12, -15 ), (  12, -15 ),
    ( -21, -14 ), (  -1, -14 ), (   1, -14 ), ( -41, -13 ), (  -5, -13 ),
    (   5, -13 ), (  21, -13 ), ( -31, -12 ), ( -15, -11 ), (  -8, -11 ),
    (   8, -11 ), (  15, -11 ), (  -2, -10 ), (   1, -10 ), (  31, -10 ),
    ( -23,  -9 ), ( -11,  -9 ), (  -5,  -9 ), (   4,  -9 ), (  11,  -9 ),
    (  42,  -9 ), (   6,  -8 ), (  24,  -8 ), ( -18,  -7 ), (  -7,  -7 ),
    (  -3,  -7 ), (  -1,  -7 ), (   2,  -7 ), (  18,  -7 ), ( -43,  -6 ),
    ( -13,  -6 ), (  -4,  -6 ), (   4,  -6 ), (   8,  -6 ), ( -33,  -5 ),
    (  -9,  -5 ), (  -2,  -5 ), (   0,  -5 ), (   2,  -5 ), (   5,  -5 ),
    (  13,  -5 ), ( -25,  -4 ), (  -6,  -4 ), (  -3,  -4 ), (   3,  -4 ),
    (   9,  -4 ), ( -19,  -3 ), (  -7,  -3 ), (  -4,  -3 ), (  -2,  -3 ),
    (  -1,  -3 ), (   0,  -3 ), (   1,  -3 ), (   2,  -3 ), (   4,  -3 ),
    (   6,  -3 ), (  33,  -3 ), ( -14,  -2 ), ( -10,  -2 ), (  -5,  -2 ),
    (  -3,  -2 ), (  -2,  -2 ), (  -1,  -2 ), (   0,  -2 ), (   1,  -2 ),
    (   2,  -2 ), (   3,  -2 ), (   5,  -2 ), (   7,  -2 ), (  14,  -2 ),
    (  19,  -2 ), (  25,  -2 ), (  43,  -2 ), (  -7,  -1 ), (  -3,  -1 ),
    (  -2,  -1 ), (  -1,  -1 ), (   0,  -1 ), (   1,  -1 ), (   2,  -1 ),
    (   3,  -1 ), (  10,  -1 ), (  -5,   0 ), (  -3,   0 ), (  -2,   0 ),
    (  -1,   0 ), (   1,   0 ), (   2,   0 ), (   3,   0 ), (   5,   0 ),
    (   7,   0 ), ( -10,   1 ), (  -7,   1 ), (  -3,   1 ), (  -2,   1 ),
    (  -1,   1 ), (   0,   1 ), (   1,   1 ), (   2,   1 ), (   3,   1 ),
    ( -43,   2 ), ( -25,   2 ), ( -19,   2 ), ( -14,   2 ), (  -5,   2 ),
    (  -3,   2 ), (  -2,   2 ), (  -1,   2 ), (   0,   2 ), (   1,   2 ),
    (   2,   2 ), (   3,   2 ), (   5,   2 ), (   7,   2 ), (  10,   2 ),
    (  14,   2 ), ( -33,   3 ), (  -6,   3 ), (  -4,   3 ), (  -2,   3 ),
    (  -1,   3 ), (   0,   3 ), (   1,   3 ), (   2,   3 ), (   4,   3 ),
    (  19,   3 ), (  -9,   4 ), (  -3,   4 ), (   3,   4 ), (   7,   4 ),
    (  25,   4 ), ( -13,   5 ), (  -5,   5 ), (  -2,   5 ), (   0,   5 ),
    (   2,   5 ), (   5,   5 ), (   9,   5 ), (  33,   5 ), (  -8,   6 ),
    (  -4,   6 ), (   4,   6 ), (  13,   6 ), (  43,   6 ), ( -18,   7 ),
    (  -2,   7 ), (   0,   7 ), (   2,   7 ), (   7,   7 ), (  18,   7 ),
    ( -24,   8 ), (  -6,   8 ), ( -42,   9 ), ( -11,   9 ), (  -4,   9 ),
    (   5,   9 ), (  11,   9 ), (  23,   9 ), ( -31,  10 ), (  -1,  10 ),
    (   2,  10 ), ( -15,  11 ), (  -8,  11 ), (   8,  11 ), (  15,  11 ),
    (  31,  12 ), ( -21,  13 ), (  -5,  13 ), (   5,  13 ), (  41,  13 ),
    (  -1,  14 ), (   1,  14 ), (  21,  14 ), ( -12,  15 ), (  12,  15 ),
    ( -39,  17 ), ( -28,  17 ), ( -18,  17 ), (  -8,  17 ), (   8,  17 ),
    (  17,  18 ), (  -4,  19 ), (   0,  19 ), (   4,  19 ), (  27,  19 ),
    (  38,  20 ), ( -13,  21 ), (  12,  22 ), ( -36,  23 ), ( -24,  23 ),
    (  -8,  24 ), (   7,  24 ), (  -3,  25 ), (   1,  25 ), (  22,  25 ),
    (  34,  26 ), ( -18,  28 ), ( -32,  29 ), (  16,  29 ), ( -11,  31 ),
    (   9,  32 ), (  29,  32 ), (  -4,  33 ), (   2,  33 ), ( -26,  34 ),
    (  23,  36 ), ( -19,  39 ), (  16,  40 ), ( -13,  41 ), (   9,  42 ),
    (  -6,  43 ), (   1,  43 ), (   0,   0 ), (   0,   0 ), (   0,   0 ),
]

def read_le_uint16(f):
    bts = bytes(x % 256 for x in f[:2])
    return struct.unpack('<H', bts)[0]

def read_le_uint32(f):
    bts = bytes(x % 256 for x in f[:4])
    return struct.unpack('<I', bts)[0]

def npoff(x):
    # This function returns the memory
    # block address of an array.
    return x.__array_interface__['data'][0]

_width = None
_height = None

_buffer = None
_bprev1 = None
_bprev2 = None
_bcurr = None

_prev_seq = None

_p4x4glyphs = None
_p8x8glyphs = None

class GlyphEdge(Enum):
    LEFT_EDGE = 0
    TOP_EDGE = 1
    RIGHT_EDGE = 2
    BOTTOM_EDGE = 3
    NO_EDGE = 4

class GlyphDir(Enum):
    DIR_LEFT = 0
    DIR_UP = 1
    DIR_RIGHT = 2
    DIR_DOWN = 3
    NO_DIR = 4

def which_edge(x, y, edge_size):
    edge_max = edge_size - 1
    if not y:
        return GlyphEdge.BOTTOM_EDGE
    elif y == edge_max:
        return GlyphEdge.TOP_EDGE
    elif not x:
        return GlyphEdge.LEFT_EDGE
    elif x == edge_max:
        return GlyphEdge.RIGHT_EDGE
    else:
        return GlyphEdge.NO_EDGE

def which_direction(edge0, edge1):
    if any((
        (edge0 == GlyphEdge.LEFT_EDGE and edge1 == GlyphEdge.RIGHT_EDGE),
        (edge1 == GlyphEdge.LEFT_EDGE and edge0 == GlyphEdge.RIGHT_EDGE),
        (edge0 == GlyphEdge.BOTTOM_EDGE and edge1 != GlyphEdge.TOP_EDGE),
        (edge1 == GlyphEdge.BOTTOM_EDGE and edge0 != GlyphEdge.TOP_EDGE)
    )):
        return GlyphDir.DIR_UP
    elif any((
        (edge0 == GlyphEdge.TOP_EDGE and edge1 != GlyphEdge.BOTTOM_EDGE),
        (edge1 == GlyphEdge.TOP_EDGE and edge0 != GlyphEdge.BOTTOM_EDGE)
    )):
        return GlyphDir.DIR_DOWN
    elif any((
        (edge0 == GlyphEdge.LEFT_EDGE and edge1 != GlyphEdge.RIGHT_EDGE),
        (edge1 == GlyphEdge.LEFT_EDGE and edge0 != GlyphEdge.RIGHT_EDGE)
    )):
        return GlyphDir.DIR_LEFT
    elif any((
        (edge0 == GlyphEdge.TOP_EDGE and edge1 == GlyphEdge.BOTTOM_EDGE),
        (edge1 == GlyphEdge.TOP_EDGE and edge0 == GlyphEdge.BOTTOM_EDGE),
        (edge0 == GlyphEdge.RIGHT_EDGE and edge1 != GlyphEdge.LEFT_EDGE),
        (edge1 == GlyphEdge.RIGHT_EDGE and edge0 != GlyphEdge.LEFT_EDGE)
    )):
        return GlyphDir.DIR_RIGHT

    return GlyphDir.NO_DIR

def interp_point(x0, y0, x1, y1, pos, npoints):
    if not npoints:
        return x0, y0
    return (
        (x0 * pos + x1 * (npoints - pos) + (npoints >> 1)) // npoints,
        (y0 * pos + y1 * (npoints - pos) + (npoints >> 1)) // npoints
    )

def make_glyphs(xvec, yvec, side_length):
    glyph_size = side_length * side_length

    for x0, y0 in zip(xvec, yvec):
        edge0 = which_edge(x0, y0, side_length)

        for x1, y1 in zip(xvec, yvec):
            pglyph = [0 for _ in range(glyph_size)]
            edge1 = which_edge(x1, y1, side_length)
            dirr = which_direction(edge0, edge1)
            npoints = max(abs(x1 - x0), abs(y1 - y0))

            for ipoint in range(npoints + 1):
                point = interp_point(x0, y0, x1, y1, ipoint, npoints)
                if dirr == GlyphDir.DIR_UP:
                    for irow in range(point[1] + 1):
                        pglyph[point[0] + irow * side_length] = 1
                elif dirr == GlyphDir.DIR_DOWN:
                    for irow in range(point[1], side_length):
                        pglyph[point[0] + irow * side_length] = 1
                elif dirr == GlyphDir.DIR_LEFT:
                    for icol in range(point[0] + 1):
                        pglyph[icol + point[1] * side_length] = 1
                elif dirr == GlyphDir.DIR_RIGHT:
                    for icol in range(point[0], side_length):
                        pglyph[icol + point[1] * side_length] = 1

            yield np.asarray(pglyph, dtype=np.uint8).reshape(side_length, side_length)

def init_codec47(width, height):
    global _width
    global _height

    global _buffer
    global _bprev1
    global _bprev2
    global _bcurr

    global _p4x4glyphs
    global _p8x8glyphs

    _width = width
    _height = height

    _p4x4glyphs = list(make_glyphs(glyph4_x, glyph4_y, 4))
    _p8x8glyphs = list(make_glyphs(glyph8_x, glyph8_y, 8))

    assert len(_p4x4glyphs) == len(_p8x8glyphs) == 256

    _buffer = np.zeros((3 * _height, _width), dtype=np.uint8)

    # initialize views of buffer
    _bprev1, _bprev2, _bcurr = (
        _buffer[:_height, :],
        _buffer[_height:2 * _height, :],
        _buffer[2 * _height:, :]
    )

def get_locs(width, height, step):
    for yloc in range(0, height, step):
        for xloc in range(0, width, step):
            yield yloc, xloc

def decode47(src, width, height):
    global _prev_seq
    global _bcurr
    global _bprev1
    global _bprev2

    if (_width, _height) != (width, height):
        print(f'init {width, height}')
        init_codec47(width, height)

    seq_nb = read_le_uint16(src)
    compression = src[2]
    rotation = src[3]
    skip = src[4]

    assert set(src[5:8]) == {0}, src[5:8]

    params = src[8:]
    bg1, bg2 = src[12:14]

    decoded_size = read_le_uint32(src[14:])
    assert decoded_size == _width * _height

    assert set(src[18:26]) == {0}, src[18:26]

    gfx_data = src[26:]
    if skip & 1:
        gfx_data = gfx_data[0x8080:]

    if seq_nb == 0:
        _bprev1[:, :] = bg1
        _bprev2[:, :] = bg2
        _prev_seq = -1

    print(f'COMPRESSION: {compression}')
    if compression == 0:
        _bcurr[:, :] = np.frombuffer(gfx_data, dtype=np.uint8).reshape((_height, _width))
    elif compression == 1:
        gfx = np.frombuffer(gfx_data, dtype=np.uint8).reshape(_height // 2, _width // 2)
        _bcurr[:, :] = gfx.repeat(2, axis=0).repeat(2, axis=1)
    elif compression == 2:
        if seq_nb == _prev_seq + 1:
            decode2(_bcurr, gfx_data, width, height, params)
            # out[:, :] = decode2(out, gfx_data, width, height, params)
    elif compression == 3:
        _bcurr[:, :] = _bprev2
    elif compression == 4:
        _bcurr[:, :] = _bprev1
    elif compression == 5:
        _bcurr[:, :] = np.asarray(bomb.decode_line(gfx_data, decoded_size), dtype=np.uint8).reshape(_height, _width)
    else:
        raise ValueError(f'Unknow compression: {compression}')

    if seq_nb == _prev_seq + 1 and rotation != 0:
        if rotation == 2:
            print('ROTATION 2')
            _bprev1, _bprev2 = _bprev2, _bprev1
        _bcurr, _bprev2 = _bprev2, _bcurr

    _prev_seq = seq_nb

    print('OFFSETS', npoff(_bcurr), npoff(_bprev1), npoff(_bprev2))

    return _bcurr.ravel().tolist()

def decode2(out, src, width, height, params):
    process_block = create_processor(
        _bprev1,
        _bprev2.ravel(),
        params
    )

    start = datetime.now()

    with io.BytesIO(src) as stream:
        for (yloc, xloc) in get_locs(width, height, 8):
            out[yloc:yloc + 8, xloc:xloc + 8] = process_block(stream, yloc, xloc, 8)

    print('processing time', str(datetime.now() - start))

    return out

def create_processor(bprev1, bprev2, params):
    def process_block(stream, yloc, xloc, size):
        code = ord(stream.read(1))

        if size == 1:
            return np.asarray([[code]], dtype=np.uint8)

        if code < 0xf8:
            mx, my = motion_vectors[code]
            off = xloc + mx + (yloc + my) * _width
            cuts = [slice(off + k * _width, off + k * _width + size) for k in range(size)]
            return np.asarray([bprev2[cut] for cut in cuts], dtype=np.uint8).reshape(size, size)
        elif code == 0xff:
            if size == 2:
                buf = stream.read(4)
                return np.frombuffer(buf, dtype=np.uint8).reshape(size, size)
            size >>= 1
            qrt1 = process_block(stream, yloc, xloc, size)
            qrt2 = process_block(stream, yloc, xloc + size, size)
            qrt3 = process_block(stream, yloc + size, xloc, size)
            qrt4 = process_block(stream, yloc + size, xloc + size, size)
            return np.block([
                [qrt1, qrt2],
                [qrt3, qrt4]
            ])
        elif code == 0xfe:
            val = ord(stream.read(1))
            return np.full((size, size), val, dtype=np.uint8)
        elif code == 0xfd:
            assert size > 2
            glyphs = _p8x8glyphs if size == 8 else _p4x4glyphs
            code = ord(stream.read(1))
            pglyph = glyphs[code]
            colors = np.frombuffer(stream.read(2), dtype=np.uint8)
            return colors[1 - pglyph]
        elif code == 0xfc:
            return bprev1[yloc:yloc + size, xloc:xloc + size]
        else:
            val = params[code & 7]
            return np.full((size, size), val, dtype=np.uint8)
    
    return process_block
