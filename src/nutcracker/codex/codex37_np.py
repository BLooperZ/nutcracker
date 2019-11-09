import io
import struct
from enum import Enum
from datetime import datetime

import numpy as np

from nutcracker.utils import funcutils
from . import bomb

maketable_bytes = (
    0,   0,   1,   0,   2,   0,   3,   0,   5,   0,
    8,   0,  13,   0,  21,   0,  -1,   0,  -2,   0,
   -3,   0,  -5,   0,  -8,   0, -13,   0, -17,   0,
  -21,   0,   0,   1,   1,   1,   2,   1,   3,   1,
    5,   1,   8,   1,  13,   1,  21,   1,  -1,   1,
   -2,   1,  -3,   1,  -5,   1,  -8,   1, -13,   1,
  -17,   1, -21,   1,   0,   2,   1,   2,   2,   2,
    3,   2,   5,   2,   8,   2,  13,   2,  21,   2,
   -1,   2,  -2,   2,  -3,   2,  -5,   2,  -8,   2,
  -13,   2, -17,   2, -21,   2,   0,   3,   1,   3,
    2,   3,   3,   3,   5,   3,   8,   3,  13,   3,
   21,   3,  -1,   3,  -2,   3,  -3,   3,  -5,   3,
   -8,   3, -13,   3, -17,   3, -21,   3,   0,   5,
    1,   5,   2,   5,   3,   5,   5,   5,   8,   5,
   13,   5,  21,   5,  -1,   5,  -2,   5,  -3,   5,
   -5,   5,  -8,   5, -13,   5, -17,   5, -21,   5,
    0,   8,   1,   8,   2,   8,   3,   8,   5,   8,
    8,   8,  13,   8,  21,   8,  -1,   8,  -2,   8,
   -3,   8,  -5,   8,  -8,   8, -13,   8, -17,   8,
  -21,   8,   0,  13,   1,  13,   2,  13,   3,  13,
    5,  13,   8,  13,  13,  13,  21,  13,  -1,  13,
   -2,  13,  -3,  13,  -5,  13,  -8,  13, -13,  13,
  -17,  13, -21,  13,   0,  21,   1,  21,   2,  21,
    3,  21,   5,  21,   8,  21,  13,  21,  21,  21,
   -1,  21,  -2,  21,  -3,  21,  -5,  21,  -8,  21,
  -13,  21, -17,  21, -21,  21,   0,  -1,   1,  -1,
    2,  -1,   3,  -1,   5,  -1,   8,  -1,  13,  -1,
   21,  -1,  -1,  -1,  -2,  -1,  -3,  -1,  -5,  -1,
   -8,  -1, -13,  -1, -17,  -1, -21,  -1,   0,  -2,
    1,  -2,   2,  -2,   3,  -2,   5,  -2,   8,  -2,
   13,  -2,  21,  -2,  -1,  -2,  -2,  -2,  -3,  -2,
   -5,  -2,  -8,  -2, -13,  -2, -17,  -2, -21,  -2,
    0,  -3,   1,  -3,   2,  -3,   3,  -3,   5,  -3,
    8,  -3,  13,  -3,  21,  -3,  -1,  -3,  -2,  -3,
   -3,  -3,  -5,  -3,  -8,  -3, -13,  -3, -17,  -3,
  -21,  -3,   0,  -5,   1,  -5,   2,  -5,   3,  -5,
    5,  -5,   8,  -5,  13,  -5,  21,  -5,  -1,  -5,
   -2,  -5,  -3,  -5,  -5,  -5,  -8,  -5, -13,  -5,
  -17,  -5, -21,  -5,   0,  -8,   1,  -8,   2,  -8,
    3,  -8,   5,  -8,   8,  -8,  13,  -8,  21,  -8,
   -1,  -8,  -2,  -8,  -3,  -8,  -5,  -8,  -8,  -8,
  -13,  -8, -17,  -8, -21,  -8,   0, -13,   1, -13,
    2, -13,   3, -13,   5, -13,   8, -13,  13, -13,
   21, -13,  -1, -13,  -2, -13,  -3, -13,  -5, -13,
   -8, -13, -13, -13, -17, -13, -21, -13,   0, -17,
    1, -17,   2, -17,   3, -17,   5, -17,   8, -17,
   13, -17,  21, -17,  -1, -17,  -2, -17,  -3, -17,
   -5, -17,  -8, -17, -13, -17, -17, -17, -21, -17,
    0, -21,   1, -21,   2, -21,   3, -21,   5, -21,
    8, -21,  13, -21,  21, -21,  -1, -21,  -2, -21,
   -3, -21,  -5, -21,  -8, -21, -13, -21, -17, -21,
    0,   0,  -8, -29,   8, -29, -18, -25,  17, -25,
    0, -23,  -6, -22,   6, -22, -13, -19,  12, -19,
    0, -18,  25, -18, -25, -17,  -5, -17,   5, -17,
  -10, -15,  10, -15,   0, -14,  -4, -13,   4, -13,
   19, -13, -19, -12,  -8, -11,  -2, -11,   0, -11,
    2, -11,   8, -11, -15, -10,  -4, -10,   4, -10,
   15, -10,  -6,  -9,  -1,  -9,   1,  -9,   6,  -9,
  -29,  -8, -11,  -8,  -8,  -8,  -3,  -8,   3,  -8,
    8,  -8,  11,  -8,  29,  -8,  -5,  -7,  -2,  -7,
    0,  -7,   2,  -7,   5,  -7, -22,  -6,  -9,  -6,
   -6,  -6,  -3,  -6,  -1,  -6,   1,  -6,   3,  -6,
    6,  -6,   9,  -6,  22,  -6, -17,  -5,  -7,  -5,
   -4,  -5,  -2,  -5,   0,  -5,   2,  -5,   4,  -5,
    7,  -5,  17,  -5, -13,  -4, -10,  -4,  -5,  -4,
   -3,  -4,  -1,  -4,   0,  -4,   1,  -4,   3,  -4,
    5,  -4,  10,  -4,  13,  -4,  -8,  -3,  -6,  -3,
   -4,  -3,  -3,  -3,  -2,  -3,  -1,  -3,   0,  -3,
    1,  -3,   2,  -3,   4,  -3,   6,  -3,   8,  -3,
  -11,  -2,  -7,  -2,  -5,  -2,  -3,  -2,  -2,  -2,
   -1,  -2,   0,  -2,   1,  -2,   2,  -2,   3,  -2,
    5,  -2,   7,  -2,  11,  -2,  -9,  -1,  -6,  -1,
   -4,  -1,  -3,  -1,  -2,  -1,  -1,  -1,   0,  -1,
    1,  -1,   2,  -1,   3,  -1,   4,  -1,   6,  -1,
    9,  -1, -31,   0, -23,   0, -18,   0, -14,   0,
  -11,   0,  -7,   0,  -5,   0,  -4,   0,  -3,   0,
   -2,   0,  -1,   0,   0, -31,   1,   0,   2,   0,
    3,   0,   4,   0,   5,   0,   7,   0,  11,   0,
   14,   0,  18,   0,  23,   0,  31,   0,  -9,   1,
   -6,   1,  -4,   1,  -3,   1,  -2,   1,  -1,   1,
    0,   1,   1,   1,   2,   1,   3,   1,   4,   1,
    6,   1,   9,   1, -11,   2,  -7,   2,  -5,   2,
   -3,   2,  -2,   2,  -1,   2,   0,   2,   1,   2,
    2,   2,   3,   2,   5,   2,   7,   2,  11,   2,
   -8,   3,  -6,   3,  -4,   3,  -2,   3,  -1,   3,
    0,   3,   1,   3,   2,   3,   3,   3,   4,   3,
    6,   3,   8,   3, -13,   4, -10,   4,  -5,   4,
   -3,   4,  -1,   4,   0,   4,   1,   4,   3,   4,
    5,   4,  10,   4,  13,   4, -17,   5,  -7,   5,
   -4,   5,  -2,   5,   0,   5,   2,   5,   4,   5,
    7,   5,  17,   5, -22,   6,  -9,   6,  -6,   6,
   -3,   6,  -1,   6,   1,   6,   3,   6,   6,   6,
    9,   6,  22,   6,  -5,   7,  -2,   7,   0,   7,
    2,   7,   5,   7, -29,   8, -11,   8,  -8,   8,
   -3,   8,   3,   8,   8,   8,  11,   8,  29,   8,
   -6,   9,  -1,   9,   1,   9,   6,   9, -15,  10,
   -4,  10,   4,  10,  15,  10,  -8,  11,  -2,  11,
    0,  11,   2,  11,   8,  11,  19,  12, -19,  13,
   -4,  13,   4,  13,   0,  14, -10,  15,  10,  15,
   -5,  17,   5,  17,  25,  17, -25,  18,   0,  18,
  -12,  19,  13,  19,  -6,  22,   6,  22,   0,  23,
  -17,  25,  18,  25,  -8,  29,   8,  29,   0,  31,
    0,   0,  -6, -22,   6, -22, -13, -19,  12, -19,
    0, -18,  -5, -17,   5, -17, -10, -15,  10, -15,
    0, -14,  -4, -13,   4, -13,  19, -13, -19, -12,
   -8, -11,  -2, -11,   0, -11,   2, -11,   8, -11,
  -15, -10,  -4, -10,   4, -10,  15, -10,  -6,  -9,
   -1,  -9,   1,  -9,   6,  -9, -11,  -8,  -8,  -8,
   -3,  -8,   0,  -8,   3,  -8,   8,  -8,  11,  -8,
   -5,  -7,  -2,  -7,   0,  -7,   2,  -7,   5,  -7,
  -22,  -6,  -9,  -6,  -6,  -6,  -3,  -6,  -1,  -6,
    1,  -6,   3,  -6,   6,  -6,   9,  -6,  22,  -6,
  -17,  -5,  -7,  -5,  -4,  -5,  -2,  -5,  -1,  -5,
    0,  -5,   1,  -5,   2,  -5,   4,  -5,   7,  -5,
   17,  -5, -13,  -4, -10,  -4,  -5,  -4,  -3,  -4,
   -2,  -4,  -1,  -4,   0,  -4,   1,  -4,   2,  -4,
    3,  -4,   5,  -4,  10,  -4,  13,  -4,  -8,  -3,
   -6,  -3,  -4,  -3,  -3,  -3,  -2,  -3,  -1,  -3,
    0,  -3,   1,  -3,   2,  -3,   3,  -3,   4,  -3,
    6,  -3,   8,  -3, -11,  -2,  -7,  -2,  -5,  -2,
   -4,  -2,  -3,  -2,  -2,  -2,  -1,  -2,   0,  -2,
    1,  -2,   2,  -2,   3,  -2,   4,  -2,   5,  -2,
    7,  -2,  11,  -2,  -9,  -1,  -6,  -1,  -5,  -1,
   -4,  -1,  -3,  -1,  -2,  -1,  -1,  -1,   0,  -1,
    1,  -1,   2,  -1,   3,  -1,   4,  -1,   5,  -1,
    6,  -1,   9,  -1, -23,   0, -18,   0, -14,   0,
  -11,   0,  -7,   0,  -5,   0,  -4,   0,  -3,   0,
   -2,   0,  -1,   0,   0, -23,   1,   0,   2,   0,
    3,   0,   4,   0,   5,   0,   7,   0,  11,   0,
   14,   0,  18,   0,  23,   0,  -9,   1,  -6,   1,
   -5,   1,  -4,   1,  -3,   1,  -2,   1,  -1,   1,
    0,   1,   1,   1,   2,   1,   3,   1,   4,   1,
    5,   1,   6,   1,   9,   1, -11,   2,  -7,   2,
   -5,   2,  -4,   2,  -3,   2,  -2,   2,  -1,   2,
    0,   2,   1,   2,   2,   2,   3,   2,   4,   2,
    5,   2,   7,   2,  11,   2,  -8,   3,  -6,   3,
   -4,   3,  -3,   3,  -2,   3,  -1,   3,   0,   3,
    1,   3,   2,   3,   3,   3,   4,   3,   6,   3,
    8,   3, -13,   4, -10,   4,  -5,   4,  -3,   4,
   -2,   4,  -1,   4,   0,   4,   1,   4,   2,   4,
    3,   4,   5,   4,  10,   4,  13,   4, -17,   5,
   -7,   5,  -4,   5,  -2,   5,  -1,   5,   0,   5,
    1,   5,   2,   5,   4,   5,   7,   5,  17,   5,
  -22,   6,  -9,   6,  -6,   6,  -3,   6,  -1,   6,
    1,   6,   3,   6,   6,   6,   9,   6,  22,   6,
   -5,   7,  -2,   7,   0,   7,   2,   7,   5,   7,
  -11,   8,  -8,   8,  -3,   8,   0,   8,   3,   8,
    8,   8,  11,   8,  -6,   9,  -1,   9,   1,   9,
    6,   9, -15,  10,  -4,  10,   4,  10,  15,  10,
   -8,  11,  -2,  11,   0,  11,   2,  11,   8,  11,
   19,  12, -19,  13,  -4,  13,   4,  13,   0,  14,
  -10,  15,  10,  15,  -5,  17,   5,  17,   0,  18,
  -12,  19,  13,  19,  -6,  22,   6,  22,   0,  23,
)

_ptable = tuple(funcutils.grouper(maketable_bytes, 2))

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
_bprev = None
_bcurr = None

_prev_seq = None

def init_codec37(width, height):
    global _width
    global _height

    global _buffer
    global _bprev
    global _bcurr

    _width = width
    _height = height

    # pad_size = 4

    _buffer = np.zeros((2 * _height, _width), dtype=np.uint8)

    # initialize views of buffer
    _bprev, _bcurr = (
        _buffer[:_height, :],
        _buffer[_height:, :]
    )

    assert _bprev.shape == _bcurr.shape == (_height, _width)


def get_locs(width, height, step):
    for yloc in range(0, height, step):
        for xloc in range(0, width, step):
            yield yloc, xloc

def decode37(src, width, height):
    global _prev_seq
    global _bcurr
    global _bprev

    if (_width, _height) != (width, height):
        print(f'init {width, height}')
        init_codec37(width, height)

    compression = src[0]
    mvoff = src[1]
    seq_nb = read_le_uint16(src[2:])
    decoded_size = read_le_uint32(src[4:])

    _unk = read_le_uint32(src[8:])

    mask_flags = src[12]
    assert set(src[13:16]) == {0}, src[13:16]

    gfx_data = src[16:]

    if compression & 5 and ((seq_nb & 1) or not (mask_flags & 1)):
        _bcurr, _bprev = _bprev, _bcurr

    if seq_nb == 0:
        print('setting bg')
        _bprev[:, :] = 0
        _prev_seq = -1

    out = _bcurr

    assert(npoff(out) == npoff(_bcurr))

    print(f'COMPRESSION: {compression}')
    if compression == 0:
        assert seq_nb == 0
        out[:, :] = np.frombuffer(gfx_data, dtype=np.uint8).reshape((_height, _width))
    elif compression == 1:
        proc1(out, gfx_data, width, height, _ptable[255 * mvoff:])
        # proc1(out, gfx_data)
    elif compression == 2:
        assert seq_nb == 0
        decoded = bomb.decode_line(gfx_data, decoded_size)
        # print(decoded[width * height:])  # might need it to fill data between buffers
        out[:, :] = np.asarray(decoded[:width * height], dtype=np.uint8).reshape(_height, _width)
    elif compression in (3, 4):
        proc37(out, gfx_data, width, height, _ptable[255 * mvoff:], (mask_flags & 4), (compression == 4))
    else:
        raise ValueError(f'Unknow compression: {compression}')

    assert(npoff(out) == npoff(_bcurr))

    print('OFFSETS', npoff(_bcurr), npoff(_bprev))

    return out.tolist()

def proc37(out, src, width, height, offsets, allow_blocks, allow_skip):
    start = datetime.now()
    with io.BytesIO(src) as stream:
        process_blocks(
            out, stream,
            height, width,
            offsets,
            allow_blocks,
            allow_skip,
        )
    print('processing time', str(datetime.now() - start))

def process_blocks(out, stream, height, width, offsets, allow_blocks, allow_skip):
    print(f'allow_blocks: {allow_blocks}, allow_skip: {allow_skip}')

    raveled = _bprev.ravel()

    skip = 0
    for (yloc, xloc) in get_locs(width, height, 4):

        if skip:
            skip -= 1
            out[yloc:yloc + 4, xloc:xloc + 4] = _bprev[yloc:yloc + 4, xloc:xloc + 4]
            continue
        code = ord(stream.read(1))

        if code == 0xff:
            out[yloc:yloc + 4, xloc:xloc + 4] = np.frombuffer(stream.read(16), dtype=np.uint8).reshape((4, 4))

        elif allow_blocks and code == 0xfe:
            val = np.frombuffer(stream.read(4), dtype=np.uint8).repeat(4, axis=0)
            out[yloc:yloc + 4, xloc:xloc + 4] = val.reshape(4, 4)

        elif allow_blocks and code == 0xfd:
            val = ord(stream.read(1))
            out[yloc:yloc + 4, xloc:xloc + 4] = val

        elif allow_skip and code == 0:
            skip = ord(stream.read(1))
            out[yloc:yloc + 4, xloc:xloc + 4] = _bprev[yloc:yloc + 4, xloc:xloc + 4]

        else:
            mx, my = offsets[code]
            by, bx = my + yloc, mx + xloc

            if 0 <= bx < bx + 4 < width and 0 <= by < by + 4 < _height:
                out[yloc:yloc + 4, xloc:xloc + 4] = _bprev[by:by + 4, bx:bx + 4]
            else:
                for k in range(4):
                    for j in range(4):
                        off = (by + k) * width + bx + j
                        out[yloc + k, xloc + j] = raveled[off] if 0 <= off < width * _height else 0


def proc1(bout, src, width, height, offsets):
    raveled = _bprev.ravel()

    code = 0
    filling = False
    skip_code = False
    ln = -1

    out = bout.ravel()

    with io.BytesIO(src) as stream:

        for (yloc, xloc) in get_locs(width, height, 4):
            if ln < 0:
                code = ord(stream.read(1))
                filling = code & 1
                ln = code >> 1
                skip_code = False
            else:
                skip_code = True

            if not filling or not skip_code:
                code = ord(stream.read(1))
                if code == 0xff:
                    ln -= 1
                    for i in range(4):
                        for j in range(4):
                            if ln < 0:
                                code = ord(stream.read(1))
                                filling = code & 1
                                ln = code >> 1
                                if filling:
                                    code = ord(stream.read(1))
                            if not filling:
                                code = ord(stream.read(1))
                            my, mx = yloc + i, xloc + j
                            if 0 <= my < height and 0 <= mx < width:
                                bout[my, mx] = code
                            ln -= 1
                    continue

            mx, my = offsets[code]
            by, bx = my + yloc, mx + xloc

            if 0 <= bx < bx + 4 < width and 0 <= by < by + 4 < _height:
                bout[yloc:yloc + 4, xloc:xloc + 4] = _bprev[by:by + 4, bx:bx + 4]
            else:
                for k in range(min(height - yloc, 4)):
                    for j in range(min(width - xloc, 4)):
                        off = (by + k) * width + bx + j
                        assert 0 <= yloc + k < height and 0 <= xloc + j < width
                        bout[yloc + k, xloc + j] = raveled[off] if 0 <= off < width * _height else 0
            ln -= 1
