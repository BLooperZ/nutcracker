#!/usr/bin/env python3

from PIL import Image
import numpy as np

def get_bg_color(row_size, f):
    BGS = [5, 4]

    def get_bg(idx):
        return BGS[f(idx) % len(BGS)]
    return get_bg

def convert_to_pil_image(frame):
    npp = np.array(frame, dtype=np.uint8)
    im = Image.fromarray(npp, mode='P')
    return im

def resize_pil_image(w, h, bg, im, loc):
    nbase = convert_to_pil_image([[bg] * w] * h)
    nbase.paste(im, box=(loc['x1'], loc['y1'], loc['x2'], loc['y2']))
    return nbase

def save_image(filename, frames, palette, h, w, transparency=None):
    palette = [x for l in palette for x in l]

    im_frames = [convert_to_pil_image(frame) for loc, frame in frames]
    locs = [loc for loc, frame in frames]

    get_bg = get_bg_color(1, lambda idx: idx)

    stack = [resize_pil_image(w, h, get_bg(idx), frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs))]

    numFrames = len(frames)
    enpp = np.array([[transparency] * w] * h * numFrames, dtype=np.uint8)
    bim = Image.fromarray(enpp, mode='P')

    for idx, frame in enumerate(stack):
        bim.paste(frame, box=(0, idx*h))

    bim.putpalette(palette)
    bim.save(filename, transparency=transparency)

def save_image_grid(filename, frames, palette, transparency=None):
    w = 32
    h = 48

    palette = [x for l in palette for x in l]

    im_frames = [convert_to_pil_image(frame) for loc, frame in frames]
    locs = [loc for loc, frame in frames]
    
    get_bg = get_bg_color(16, lambda idx: idx + int(idx / 16))

    stack = [resize_pil_image(w, h, get_bg(idx), frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs))]

    enpp = np.array([[transparency] * w * 16] * h * 16, dtype=np.uint8)
    bim = Image.fromarray(enpp, mode='P')

    for idx, frame in enumerate(stack):
        bim.paste(frame, box=((idx % 16) * w, int(idx / 16) * h))

    palette[39*3] = 109
    palette[39*3+1] = 109
    palette[39*3+1] = 109
    bim.putpalette(palette)
    bim.save(filename) #, transparency=transparency)
