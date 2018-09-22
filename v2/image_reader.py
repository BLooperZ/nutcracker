#!/usr/bin/env python3

from PIL import Image
import numpy as np
from struct import Struct
from itertools import takewhile

PALETTE_SIZE = 256
palette_struct = Struct('<{}B'.format(3 * PALETTE_SIZE))

def read_image_grid(filename):
    w = 32
    h = 48

    bim = Image.open(filename)

    # mode = bim.mode
    # print((mode))
    # if mode != 'P':
    #     bim.convert('P')

    color_mode, palette = bim.palette.getdata()
    palette = palette_struct.unpack(palette)
    palette = [palette[3*i:3*i+3] for i in range(256)]

    for row in range(16):
        for col in range(16):
            area = (col * w, row * h, (col + 1) * w, (row + 1) * h)
            yield bim.crop(area)

def count_in_row(pred, row):
    return sum(1 for _ in takewhile(pred, row))

def resize_frame(im):
    BGS = [5, 4]
    char_is_bg = lambda c: c in BGS
    line_is_bg = lambda line: all(c in BGS for c in line)

    frame = list(np.asarray(im))

    x1 = min(count_in_row(char_is_bg, line) for line in frame)
    x2 = len(frame[0]) - min(count_in_row(char_is_bg, reversed(line)) for line in frame)
    y1 = count_in_row(line_is_bg, frame)
    y2 = len(frame) - count_in_row(line_is_bg, reversed(frame))

    area = (x1, y1, x2, y2)

    if area == (0, 0, len(frame[0]), len(frame)):
        return None

    fields = ('x1', 'y1', 'x2', 'y2')
    loc = dict(zip(fields, area))

    return loc, list(np.asarray(im.crop(area)))

if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--codec', '-c', action='store', required=True, help='codec for encoding', choices=[21, 44])
    args = parser.parse_args()

    frames = read_image_grid(args.filename)
    frames = (resize_frame(frame) for frame in frames)
    for loc, frame in frames:
        print(loc)

