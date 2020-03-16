#!/usr/bin/env python3
import io
import math
import struct
from itertools import chain, takewhile
from functools import partial
from operator import itemgetter
from typing import Set

import numpy as np

from nutcracker.utils.funcutils import grouper, flatten
from nutcracker.codex.rle import encode_lined_rle
from nutcracker.graphics import grid
from .bpp_codec import decode_bpp_char, encode_bpp_char


def calc_bpp(x):
    return 1 << max((x - 1).bit_length() - 1, 0).bit_length()

# TODO: replace with itertools.takewhile
def filter_empty_frames(frames):
    for im in frames:
        frame = list(np.asarray(im))
        if set(flatten(frame)) == {0}:
            break
        yield im

def bind(func, frames):
    for frame in frames:
        yield frame, func(frame) if frame else None

def get_frame_bpp(frame):
    return calc_bpp(len(set(flatten(frame[1]))))

def encode_frames(frames, encoder):
    for idx, frame in enumerate(frames):
        if not frame:
            yield None
        else:
            print(idx)
            loc, img = frame
            with io.BytesIO() as stream:
                width = loc['x2'] - loc['x1']
                assert width == len(img[0])
                cheight = loc['y2'] - loc['y1']
                assert cheight == len(img)
                xoff = loc['x1']
                yoff = loc['y1']
                yield struct.pack('<2B2b', width, cheight, xoff, yoff) + encoder(img)

if __name__ == '__main__':
    import argparse
    import os

    from .preset import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--ref', '-r', action='store', type=str, help='reference CHAR file')
    parser.add_argument('--target', '-t', help='target file', default='CHAR_OUT')
    args = parser.parse_args()

    with open(args.ref, 'rb') as ref:
        data = sputm.assert_tag('CHAR', sputm.untag(ref))
        assert ref.read() == b''
        with io.BytesIO(data) as stream:
            stream.seek(0, io.SEEK_END)
            dataend_real = stream.tell() - 4
            stream.seek(0, io.SEEK_SET)
            dataend = int.from_bytes(stream.read(4), byteorder='little', signed=False)
            dataend_diff = dataend_real - dataend
            version = ord(stream.read(1))       
            color_map = stream.read(16)
            bpp = ord(stream.read(1))
            height = ord(stream.read(1))
            print(dataend_diff, version, color_map, bpp, height)

    frames = grid.read_image_grid(args.filename)
    frames = list(filter_empty_frames(frames))
    while not frames[-1]:
        frames = frames[:-1]
    nchars = len(frames)
    print(nchars)
    frames = (grid.resize_frame(frame) for frame in frames)
    frames, bpps = zip(*bind(get_frame_bpp, frames))

    v_bpp = max(val for val in bpps if val)
    print(f'{v_bpp}v_bpp, {bpp}bpp')
    assert v_bpp <= bpp, (bpp, v_bpp)
    encoder = partial(encode_bpp_char, bpp=bpp) if bpp in (1, 2, 4) else encode_lined_rle
    frames = list(encode_frames(frames, encoder))
    assert nchars == len(frames)
    with io.BytesIO() as data_stream, io.BytesIO() as idx_stream:
        idx_stream.write(version.to_bytes(1, byteorder='little', signed=False))
        idx_stream.write(color_map)
        idx_stream.write(bpp.to_bytes(1, byteorder='little', signed=False))
        idx_stream.write(height.to_bytes(1, byteorder='little', signed=False))
        idx_stream.write(nchars.to_bytes(2, byteorder='little', signed=False))
        offset = idx_stream.tell() - 17 + 4 * nchars
        for frame in frames:
            if not frame:
                idx_stream.write(b'\00\00\00\00')
            else:
                print(frame)
                data_stream.write(frame)
                idx_stream.write(offset.to_bytes(4, byteorder='little', signed=False))
                offset += len(frame)
        out_data = idx_stream.getvalue() + data_stream.getvalue()
        out = (len(out_data) - dataend_diff).to_bytes(4, byteorder='little', signed=False) + out_data
    with open(args.target, 'wb') as outfile:
        outfile.write(sputm.mktag('CHAR', out))
