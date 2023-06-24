# TODO: rename to blocky8

import io
import logging
import struct
from datetime import datetime
from enum import Enum

import numpy as np

from . import bomp

# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

glyph4_xy = tuple(
    zip(
        (0, 1, 2, 3, 3, 3, 3, 2, 1, 0, 0, 0, 1, 2, 2, 1),
        (0, 0, 0, 0, 1, 2, 3, 3, 3, 3, 2, 1, 1, 1, 2, 2),
    )
)

glyph8_xy = tuple(
    zip(
        (0, 2, 5, 7, 7, 7, 7, 7, 7, 5, 2, 0, 0, 0, 0, 0),
        (0, 0, 0, 0, 1, 3, 4, 6, 7, 7, 7, 7, 6, 4, 3, 1),
    )
)

# fmt: off
motion_vectors = (
    (  0,   0), ( -1, -43), (  6, -43), ( -9, -42), ( 13, -41),
    (-16, -40), ( 19, -39), (-23, -36), ( 26, -34), ( -2, -33),
    (  4, -33), (-29, -32), ( -9, -32), ( 11, -31), (-16, -29),
    ( 32, -29), ( 18, -28), (-34, -26), (-22, -25), ( -1, -25),
    (  3, -25), ( -7, -24), (  8, -24), ( 24, -23), ( 36, -23),
    (-12, -22), ( 13, -21), (-38, -20), (  0, -20), (-27, -19),
    ( -4, -19), (  4, -19), (-17, -18), ( -8, -17), (  8, -17),
    ( 18, -17), ( 28, -17), ( 39, -17), (-12, -15), ( 12, -15),
    (-21, -14), ( -1, -14), (  1, -14), (-41, -13), ( -5, -13),
    (  5, -13), ( 21, -13), (-31, -12), (-15, -11), ( -8, -11),
    (  8, -11), ( 15, -11), ( -2, -10), (  1, -10), ( 31, -10),
    (-23,  -9), (-11,  -9), ( -5,  -9), (  4,  -9), ( 11,  -9),
    ( 42,  -9), (  6,  -8), ( 24,  -8), (-18,  -7), ( -7,  -7),
    ( -3,  -7), ( -1,  -7), (  2,  -7), ( 18,  -7), (-43,  -6),
    (-13,  -6), ( -4,  -6), (  4,  -6), (  8,  -6), (-33,  -5),
    ( -9,  -5), ( -2,  -5), (  0,  -5), (  2,  -5), (  5,  -5),
    ( 13,  -5), (-25,  -4), ( -6,  -4), ( -3,  -4), (  3,  -4),
    (  9,  -4), (-19,  -3), ( -7,  -3), ( -4,  -3), ( -2,  -3),
    ( -1,  -3), (  0,  -3), (  1,  -3), (  2,  -3), (  4,  -3),
    (  6,  -3), ( 33,  -3), (-14,  -2), (-10,  -2), ( -5,  -2),
    ( -3,  -2), ( -2,  -2), ( -1,  -2), (  0,  -2), (  1,  -2),
    (  2,  -2), (  3,  -2), (  5,  -2), (  7,  -2), ( 14,  -2),
    ( 19,  -2), ( 25,  -2), ( 43,  -2), ( -7,  -1), ( -3,  -1),
    ( -2,  -1), ( -1,  -1), (  0,  -1), (  1,  -1), (  2,  -1),
    (  3,  -1), ( 10,  -1), ( -5,   0), ( -3,   0), ( -2,   0),
    ( -1,   0), (  1,   0), (  2,   0), (  3,   0), (  5,   0),
    (  7,   0), (-10,   1), ( -7,   1), ( -3,   1), ( -2,   1),
    ( -1,   1), (  0,   1), (  1,   1), (  2,   1), (  3,   1),
    (-43,   2), (-25,   2), (-19,   2), (-14,   2), ( -5,   2),
    ( -3,   2), ( -2,   2), ( -1,   2), (  0,   2), (  1,   2),
    (  2,   2), (  3,   2), (  5,   2), (  7,   2), ( 10,   2),
    ( 14,   2), (-33,   3), ( -6,   3), ( -4,   3), ( -2,   3),
    ( -1,   3), (  0,   3), (  1,   3), (  2,   3), (  4,   3),
    ( 19,   3), ( -9,   4), ( -3,   4), (  3,   4), (  7,   4),
    ( 25,   4), (-13,   5), ( -5,   5), ( -2,   5), (  0,   5),
    (  2,   5), (  5,   5), (  9,   5), ( 33,   5), ( -8,   6),
    ( -4,   6), (  4,   6), ( 13,   6), ( 43,   6), (-18,   7),
    ( -2,   7), (  0,   7), (  2,   7), (  7,   7), ( 18,   7),
    (-24,   8), ( -6,   8), (-42,   9), (-11,   9), ( -4,   9),
    (  5,   9), ( 11,   9), ( 23,   9), (-31,  10), ( -1,  10),
    (  2,  10), (-15,  11), ( -8,  11), (  8,  11), ( 15,  11),
    ( 31,  12), (-21,  13), ( -5,  13), (  5,  13), ( 41,  13),
    ( -1,  14), (  1,  14), ( 21,  14), (-12,  15), ( 12,  15),
    (-39,  17), (-28,  17), (-18,  17), ( -8,  17), (  8,  17),
    ( 17,  18), ( -4,  19), (  0,  19), (  4,  19), ( 27,  19),
    ( 38,  20), (-13,  21), ( 12,  22), (-36,  23), (-24,  23),
    ( -8,  24), (  7,  24), ( -3,  25), (  1,  25), ( 22,  25),
    ( 34,  26), (-18,  28), (-32,  29), ( 16,  29), (-11,  31),
    (  9,  32), ( 29,  32), ( -4,  33), (  2,  33), (-26,  34),
    ( 23,  36), (-19,  39), ( 16,  40), (-13,  41), (  9,  42),
    ( -6,  43), (  1,  43), (  0,   0), (  0,   0), (  0,   0),
)
# fmt: on


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
    if any(
        (
            (edge0 == GlyphEdge.LEFT_EDGE and edge1 == GlyphEdge.RIGHT_EDGE),
            (edge1 == GlyphEdge.LEFT_EDGE and edge0 == GlyphEdge.RIGHT_EDGE),
            (edge0 == GlyphEdge.BOTTOM_EDGE and edge1 != GlyphEdge.TOP_EDGE),
            (edge1 == GlyphEdge.BOTTOM_EDGE and edge0 != GlyphEdge.TOP_EDGE),
        )
    ):
        return GlyphDir.DIR_UP
    elif any(
        (
            (edge0 == GlyphEdge.TOP_EDGE and edge1 != GlyphEdge.BOTTOM_EDGE),
            (edge1 == GlyphEdge.TOP_EDGE and edge0 != GlyphEdge.BOTTOM_EDGE),
        )
    ):
        return GlyphDir.DIR_DOWN
    elif any(
        (
            (edge0 == GlyphEdge.LEFT_EDGE and edge1 != GlyphEdge.RIGHT_EDGE),
            (edge1 == GlyphEdge.LEFT_EDGE and edge0 != GlyphEdge.RIGHT_EDGE),
        )
    ):
        return GlyphDir.DIR_LEFT
    elif any(
        (
            (edge0 == GlyphEdge.TOP_EDGE and edge1 == GlyphEdge.BOTTOM_EDGE),
            (edge1 == GlyphEdge.TOP_EDGE and edge0 == GlyphEdge.BOTTOM_EDGE),
            (edge0 == GlyphEdge.RIGHT_EDGE and edge1 != GlyphEdge.LEFT_EDGE),
            (edge1 == GlyphEdge.RIGHT_EDGE and edge0 != GlyphEdge.LEFT_EDGE),
        )
    ):
        return GlyphDir.DIR_RIGHT

    return GlyphDir.NO_DIR


def interp_point(x0, y0, x1, y1, pos, npoints):
    if not npoints:
        return x0, y0
    return (
        (x0 * pos + x1 * (npoints - pos) + (npoints >> 1)) // npoints,
        (y0 * pos + y1 * (npoints - pos) + (npoints >> 1)) // npoints,
    )


def make_glyphs(vecs, side_length):
    for x0, y0 in vecs:
        edge0 = which_edge(x0, y0, side_length)

        for x1, y1 in vecs:
            edge1 = which_edge(x1, y1, side_length)
            dirr = which_direction(edge0, edge1)
            npoints = max(abs(x1 - x0), abs(y1 - y0))

            npglyph = np.zeros((side_length, side_length), dtype=np.uint8)

            for ipoint in range(npoints + 1):
                p0, p1 = interp_point(x0, y0, x1, y1, ipoint, npoints)
                if dirr == GlyphDir.DIR_UP:
                    npglyph[: p1 + 1, p0] = 1
                elif dirr == GlyphDir.DIR_DOWN:
                    npglyph[p1:, p0] = 1
                elif dirr == GlyphDir.DIR_LEFT:
                    npglyph[p1, : p0 + 1] = 1
                elif dirr == GlyphDir.DIR_RIGHT:
                    npglyph[p1, p0:] = 1
            yield npglyph


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

    _p4x4glyphs = tuple(make_glyphs(glyph4_xy, 4))
    _p8x8glyphs = tuple(make_glyphs(glyph8_xy, 8))

    assert len(_p4x4glyphs) == len(_p8x8glyphs) == 256

    _buffer = np.zeros((3 * _height, _width), dtype=np.uint8)

    # initialize views of buffer
    _bprev1, _bprev2, _bcurr = (
        _buffer[:_height, :],
        _buffer[_height : 2 * _height, :],
        _buffer[2 * _height :, :],
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

    out = _bcurr

    assert npoff(out) == npoff(_bcurr)

    print(f'COMPRESSION: {compression}')
    if compression == 0:
        out[:, :] = np.frombuffer(gfx_data, dtype=np.uint8).reshape((_height, _width))
    elif compression == 1:
        gfx = np.frombuffer(gfx_data, dtype=np.uint8).reshape(_height // 2, _width // 2)
        out[:, :] = gfx.repeat(2, axis=0).repeat(2, axis=1)
    elif compression == 2:
        if seq_nb == _prev_seq + 1:

            logging.debug('FIRST DECODE')
            decode2(out, gfx_data, width, height, params)

            # # TEST ENCODING DIFF:
            # logging.debug('==========================================================')
            # logging.debug('ENCODE')
            # newgfx = encode2(out, width, height, params)

            # assert len(newgfx) <= len(gfx_data)
            # out2 = np.zeros((_height, _width), dtype=np.uint8)
            # logging.debug('==========================================================')
            # logging.debug('SECOND DECODE')
            # decode2(out2, newgfx, width, height, params)
            # assert np.array_equal(out, out2)
            # exit(0)
            # out[:, :] = decode2(out, gfx_data, width, height, params)

    elif compression == 3:
        out[:, :] = _bprev2
    elif compression == 4:
        out[:, :] = _bprev1
    elif compression == 5:
        out[:, :] = np.frombuffer(
            bomp.decode_line(gfx_data, decoded_size), dtype=np.uint8
        ).reshape(_height, _width)
    else:
        raise ValueError(f'Unknown compression: {compression}')

    assert npoff(out) == npoff(_bcurr)

    if seq_nb == _prev_seq + 1 and rotation != 0:
        if rotation == 2:
            print('ROTATION 2')
            _bprev1, _bprev2 = _bprev2, _bprev1
        _bcurr, _bprev2 = _bprev2, _bcurr

    _prev_seq = seq_nb

    print('OFFSETS', npoff(_bcurr), npoff(_bprev1), npoff(_bprev2))

    return out.tolist()


_params = None
_strided = None


def rollable_view(ndarr, max_overflow=None):
    rows, cols = ndarr.shape
    ncols = cols + max_overflow if max_overflow else rows * cols
    return np.lib.stride_tricks.as_strided(
        ndarr, (rows, ncols), ndarr.strides, writeable=False
    )


def decode2(out, src, width, height, params):
    global _params
    global _strided

    _params = params
    _strided = rollable_view(_bprev2, max_overflow=8)

    assert npoff(_strided) == npoff(_bprev2)

    start = datetime.now()
    with io.BytesIO(src) as stream:
        for (yloc, xloc) in get_locs(width, height, 8):
            process_block(out[yloc : yloc + 8, xloc : xloc + 8], stream, yloc, xloc, 8)
    print('processing time', str(datetime.now() - start))


def process_block(out, stream, yloc, xloc, size):
    pos = stream.tell()
    logging.debug((pos, yloc, xloc, size))
    code = ord(stream.read(1))

    if size == 1:
        out[:, :] = code

    if code < 0xF8:
        mx, my = motion_vectors[code]
        by, bx = my + yloc, mx + xloc

        by, bx = by + bx // _width, bx % _width
        assert 0 <= by < _height, (by, _height)
        assert 0 <= bx < _width, (bx, _width)

        if (by + size - 1) * _width + bx + size - 1 >= _width * _height:
            raise IndexError(f'out of bounds: {by}, {bx}, {size}')

        out[:, :] = _strided[by : by + size, bx : bx + size]
        logging.debug(out[:, :])
        logging.debug((size, bytes([code])))

    elif code == 0xFF:
        logging.debug((size, bytes([code])))
        if size == 2:
            buf = stream.read(4)
            out[:, :] = np.frombuffer(buf, dtype=np.uint8).reshape(size, size)
        else:
            size >>= 1
            process_block(out[:size, :size], stream, yloc, xloc, size)
            process_block(out[:size, size:], stream, yloc, xloc + size, size)
            process_block(out[size:, :size], stream, yloc + size, xloc, size)
            process_block(out[size:, size:], stream, yloc + size, xloc + size, size)
    elif code == 0xFE:
        val = ord(stream.read(1))
        out[:, :] = val
        logging.debug(out[:, :])
        logging.debug((size, bytes([code, val])))
    elif code == 0xFD:
        assert size > 2, stream.tell()
        glyphs = _p8x8glyphs if size == 8 else _p4x4glyphs
        gcode = ord(stream.read(1))
        pglyph = glyphs[gcode]
        colors = np.frombuffer(stream.read(2), dtype=np.uint8)
        out[:, :] = colors[1 - pglyph]
        logging.debug(out[:, :])
        logging.debug((size, bytes([code, gcode, *colors])))
    elif code == 0xFC:
        out[:, :] = _bprev1[yloc : yloc + size, xloc : xloc + size]
        logging.debug(out[:, :])
        logging.debug((size, bytes([code])))
    else:
        val = _params[code & 7]
        out[:, :] = val
        logging.debug(out[:, :])
        logging.debug((size, bytes([code])))


def encode2(frame, width, height, params):
    global _params
    global _strided

    _params = params
    _strided = rollable_view(_bprev2, max_overflow=8)

    assert npoff(_strided) == npoff(_bprev2)

    start = datetime.now()
    with io.BytesIO() as stream:
        for (yloc, xloc) in get_locs(width, height, 8):
            encode_block(frame[yloc : yloc + 8, xloc : xloc + 8], stream, yloc, xloc, 8)
        print('processing time', str(datetime.now() - start))
        return stream.getvalue()


def encode_block(frame, stream, yloc, xloc, size):
    logging.debug((stream.tell(), yloc, xloc, size))

    for idx, (mx, my) in enumerate(motion_vectors[:0xF8]):
        by, bx = my + yloc, mx + xloc
        by, bx = by + bx // _width, bx % _width
        if (0 <= by < _height) and (0 <= bx < _width):
            if (by + size - 1) * _width + bx + size - 1 >= _width * _height:
                logging.debug(f'out of bounds: {by}, {bx}, {size}')
                continue
            if np.array_equal(frame, _strided[by : by + size, bx : bx + size]):
                stream.write(bytes([idx]))
                logging.debug(frame)
                logging.debug((size, bytes([idx])))
                return

    if np.array_equal(frame, _bprev1[yloc : yloc + size, xloc : xloc + size]):
        stream.write(bytes([0xFC]))
        logging.debug(frame)
        logging.debug((size, bytes([0xFC])))
        return

    for idx, color in enumerate(_params[:4]):
        assert 0 <= idx < 4
        if np.all(frame == color):
            stream.write(bytes([idx + 0xF8]))
            logging.debug(frame)
            logging.debug((size, bytes([idx + 0xF8])))
            return

    if (frame == frame[0, 0]).sum() == len(frame.ravel()):
        stream.write(bytes([0xFE, frame[0, 0]]))
        logging.debug(frame)
        logging.debug((size, bytes([0xFE, frame[0, 0]])))
        return

    if size > 2:
        glyphs = _p8x8glyphs if size == 8 else _p4x4glyphs
        colors = np.asarray(list(set(frame.ravel())), dtype=np.uint8)
        if len(colors) == 2:
            for idx, glyph in enumerate(glyphs):
                cglyph = colors[1 - glyph]
                if np.array_equal(cglyph, frame):
                    stream.write(bytes([0xFD, idx, *colors]))
                    logging.debug(frame)
                    logging.debug((size, bytes([0xFD, idx, *colors])))
                    return
                rglyph = colors[glyph]
                if np.array_equal(rglyph, frame):
                    stream.write(bytes([0xFD, idx, *colors[::-1]]))
                    logging.debug(frame)
                    logging.debug((size, bytes([0xFD, idx, *colors[::-1]])))
                    return

    stream.write(bytes([0xFF]))
    logging.debug((size, bytes([0xFF])))
    if size == 2:
        stream.write(frame.tobytes())
        logging.debug(frame)
        logging.debug((frame.tobytes()))
        return
    size >>= 1
    encode_block(frame[:size, :size], stream, yloc, xloc, size)
    encode_block(frame[:size, size:], stream, yloc, xloc + size, size)
    encode_block(frame[size:, :size], stream, yloc + size, xloc, size)
    encode_block(frame[size:, size:], stream, yloc + size, xloc + size, size)
    return


def fake_encode47(out, bg1=b'\0', bg2=b'\0'):
    # from . import codex47_np as cdx

    width = len(out[0])
    height = len(out)
    print(width, height)

    seq_nb = b'\0\0'
    compression = b'\0'
    rotation = b'\0'
    skip = b'\0'
    _dummy = b'\0\0\0'
    params = b'\0\0\0\0'
    bg1 = bg1
    bg2 = bg2

    decoded_size = struct.pack('<I', width * height)

    _dummy2 = b'\0' * 8

    return (
        seq_nb
        + compression
        + rotation
        + skip
        + _dummy
        + params
        + bg1
        + bg2
        + decoded_size
        + _dummy2
        + b''.join(out)
    )
