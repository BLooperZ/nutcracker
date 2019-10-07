import itertools

import numpy as np
from PIL import Image

from utils import funcutils
from .base import convert_to_pil_image

BGS = [b'0', b'n']
BASE_XOFF = 8
BASE_YOFF = 8
TILE_W = 48 + BASE_XOFF
TILE_H = 48 + BASE_YOFF
GRID_SIZE = 16

def get_bg_color(row_size, f):
    def get_bg(idx):
        return ord(BGS[f(idx) % len(BGS)])
    return get_bg

def read_image_grid(filename, w=TILE_W, h=TILE_H, grid_size=GRID_SIZE):
    bim = Image.open(filename)

    for row in range(grid_size):
        for col in range(grid_size):
            area = (col * w, row * h, (col + 1) * w, (row + 1) * h)
            yield bim.crop(area)

def checkered_grid(nchars, w=TILE_W, h=TILE_H, grid_size=GRID_SIZE):
    assert nchars <= grid_size ** 2, nchars

    bim = convert_to_pil_image([[0] * w * grid_size] * h * grid_size)
    get_bg = get_bg_color(grid_size, lambda idx: idx + int(idx / grid_size))

    # nchars does not have to match real number of characters nor max. index
    for i in range(nchars):
        ph = convert_to_pil_image([[get_bg(i)] * w] * h)
        bim.paste(ph, box=((i % grid_size) * w, int(i / grid_size) * h))

    return bim

def create_char_grid(nchars, chars, w=TILE_W, h=TILE_H, grid_size=GRID_SIZE, base_xoff=BASE_XOFF, base_yoff=BASE_YOFF):
    bim = checkered_grid(nchars, w=w, h=h, grid_size=grid_size)

    # idx is character index in ascii table
    for idx, (xoff, yoff, im) in chars:
        assert idx < nchars
        xbase = (idx % grid_size) * w + base_xoff
        ybase = (idx // grid_size) * h + base_yoff
        bim.paste(im, box=(xbase + xoff, ybase + yoff))

    return bim

def count_in_row(pred, row):
    return sum(1 for _ in itertools.takewhile(pred, row))

def resize_frame(im, base_xoff=BASE_XOFF, base_yoff=BASE_YOFF):
    frame = list(np.asarray(im))
    BG = frame[-1][-1]

    char_is_bg = lambda c: c == BG
    line_is_bg = lambda line: all(c == BG for c in line)

    if set(funcutils.flatten(frame)) == {BG}:
        return None

    x1 = min(count_in_row(char_is_bg, line) for line in frame)
    x2 = len(frame[0]) - min(count_in_row(char_is_bg, reversed(line)) for line in frame)
    y1 = count_in_row(line_is_bg, frame)
    y2 = len(frame) - count_in_row(line_is_bg, reversed(frame))

    crop_area = (x1, y1, x2, y2)

    if crop_area == (0, 0, len(frame[0]), len(frame)):
        return None

    off_area = (x1 - base_xoff, y1 - base_yoff, x2 - base_xoff, y2 - base_yoff)

    fields = ('x1', 'y1', 'x2', 'y2')
    loc = dict(zip(fields, off_area))

    return loc, np.asarray(im.crop(crop_area))
