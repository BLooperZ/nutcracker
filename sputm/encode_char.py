#!/usr/bin/env python3
import io
import math
import struct
from itertools import chain, takewhile
from functools import partial
from operator import itemgetter

import numpy as np
from PIL import Image

from utils.funcutils import grouper, flatten
from .bpp_codec import decode_bpp_char, encode_bpp_char

from typing import Set

def decode_lined_rle(data, width, height):
    datlen = len(data)

    output = [[0 for _ in range(width)] for _ in range(height)]

    pos = 0
    next_pos = pos
    for curry in range(height):
    # while pos < datlen and curry < height:
        currx = 0
        bytecount = int.from_bytes(data[next_pos:next_pos + 2], byteorder='little', signed=False)
        pos = next_pos + 2
        next_pos += bytecount + 2
        while pos < datlen and pos < next_pos:
            code = data[pos]
            pos += 1
            if code & 1:  # skip count
                currx += (code >> 1)
            else:
                count = (code >> 2) + 1
                if code & 2:  # encoded run
                    output[curry][currx:currx+count] = [data[pos]] * count
                    pos += 1
                else:  # absolute run
                    output[curry][currx:currx+count] = data[pos:pos+count]
                    pos += count
                currx += count
            assert not currx > width
    return output

def handle_char(data):
    with io.BytesIO(data) as stream:
        stream.seek(0, 2)
        dataend_real = stream.tell()
        print(dataend_real - 21)
        stream.seek(0, 0)
        dataend = int.from_bytes(stream.read(4), byteorder='little', signed=False) - 6
        print(dataend)
        datastart = 21
        version = ord(stream.read(1))
        color_map = stream.read(16)
        assert stream.tell() == datastart

        bpp = ord(stream.read(1))
        print(f'{bpp}bpp')
        decoder = partial(decode_bpp_char, bpp=bpp) if bpp in (1, 2, 4) else decode_lined_rle

        height = ord(stream.read(1))

        nchars = int.from_bytes(stream.read(2), byteorder='little', signed=False)

        assert stream.tell() == datastart + 4
        offs = [int.from_bytes(stream.read(4), byteorder='little', signed=False) for i in range(nchars)]
        print(offs)
        offs = [off for off in enumerate(offs) if off[1] != 0]

        index = list(zip(offs, [off[1] for off in offs[1:]] + [dataend]))
        print(len(index), index)
        # print(version, color_map, bpp, height, nchars, offs, stream.read())

        unique_vals: Set[int] = set()
        for (idx, off), nextoff in index:
            size = nextoff - off - 4
            assert stream.tell() == datastart + off
            width = ord(stream.read(1))
            cheight = ord(stream.read(1))
            off1 = ord(stream.read(1))
            off2 = ord(stream.read(1))
            if not (off1 == 0 and off2 == 0):
                print('OFFSET', idx, off1, off2)
            char = decoder(stream.read(size), width, cheight)
            unique_vals |= set(chain.from_iterable(char))
            yield idx, convert_to_pil_image(char, width, cheight)
            # print(len(dt), height, width, cheight, off1, off2, bpp)
        print(unique_vals)

def read_image_grid(filename):
    w = 48
    h = 48

    bim = Image.open(filename)

    for row in range(16):
        for col in range(16):
            area = (col * w, row * h, (col + 1) * w, (row + 1) * h)
            yield bim.crop(area)

def resize_pil_image(w, h, bg, im):
    # print(bg)
    nbase = convert_to_pil_image(bytes(bg) * w * h, w, h)
    # nbase.paste(im, box=itemgetter('x1', 'y1', 'x2', 'y2')(loc))
    nbase.paste(im, box=(0, 0))
    return nbase

def count_in_row(pred, row):
    return sum(1 for _ in takewhile(pred, row))

def calc_bpp(x):
    return 1 << max((x - 1).bit_length() - 1, 0).bit_length()

def resize_frame(im):
    frame = list(np.asarray(im))
    BG = frame[-1][-1]

    char_is_bg = lambda c: c == BG
    line_is_bg = lambda line: all(c == BG for c in line)

    if set(flatten(frame)) == {BG}:
        return None

    x1 = min(count_in_row(char_is_bg, line) for line in frame)
    x2 = len(frame[0]) - min(count_in_row(char_is_bg, reversed(line)) for line in frame)
    y1 = count_in_row(line_is_bg, frame)
    y2 = len(frame) - count_in_row(line_is_bg, reversed(frame))

    area = (x1, y1, x2, y2)

    if area == (0, 0, len(frame[0]), len(frame)):
        return None

    fields = ('x1', 'y1', 'x2', 'y2')
    loc = dict(zip(fields, area))

    return loc, np.asarray(im.crop(area))

def bind(func, frames):
    for frame in frames:
        yield frame, func(frame) if frame else None

def encode_lined_rle(char):
    return b'\0'

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
                off1 = loc['x1']
                off2 = loc['y1']
                yield struct.pack('<4B', width, cheight, off1, off2) + encoder(img)

if __name__ == '__main__':
    import argparse
    import os

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--ref', '-r', action='store', type=str, help='reference CHAR file')
    args = parser.parse_args()

    with open(args.ref, 'rb') as ref:
        data = sputm.assert_tag('CHAR', sputm.untag(ref))
        assert ref.read() == b''
        with io.BytesIO(data) as stream:
            stream.seek(4, io.SEEK_SET)
            version = ord(stream.read(1))       
            color_map = stream.read(16)
            ref_bpp = ord(stream.read(1))
            height = ord(stream.read(1))

    frames = read_image_grid(args.filename)
    frames = (resize_frame(frame) for frame in frames)
    frames, bpps = zip(*bind(get_frame_bpp, frames))

    bpp = max(val for val in bpps if val)
    print(f'{bpp}bpp')
    assert bpp == ref_bpp

    encoder = partial(encode_bpp_char, bpp=bpp) if bpp in (1, 2, 4) else encode_lined_rle
    frames = list(encode_frames(frames, encoder))
    while not frames[-1]:
        frames = frames[:-1]
    nchars = len(frames)
    print(nchars)
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
        out = (len(out_data) - 11).to_bytes(4, byteorder='little', signed=False) + out_data
    with open('OUTPUT.CHAR', 'wb') as outfile:
        outfile.write(sputm.mktag('CHAR', out))
