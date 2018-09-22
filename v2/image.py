#!/usr/bin/env python3

from PIL import Image, TiffImagePlugin, ImageChops
import numpy as np

def convert_to_pil_image(frame):
    npp = np.array(frame, dtype=np.uint8)
    im = Image.fromarray(npp, mode='P')
    return im

def resize_pil_image(w, h, bg, im, loc):
    nbase = convert_to_pil_image([[bg] * w] * h)
    nbase.paste(im, box=(loc['x1'], loc['y1'], loc['x2'], loc['y2']))
    return nbase

def save_image(filename, frames, palette, h, w, transparency=None):
    palette = list(palette)
    palette = [x for l in palette for x in l]

    im_frames = [convert_to_pil_image(frame) for loc, frame in frames]
    locs = [loc for loc, frame in frames]
    BGS = [5, 4]
    stack = [resize_pil_image(w, h, BGS[idx % 2], frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs))]

    numFrames = len(frames)
    enpp = np.array([[transparency] * w] * h * numFrames, dtype=np.uint8)
    bim = Image.fromarray(enpp, mode='P')

    for idx, frame in enumerate(stack):
        bim.paste(frame, box=(0, idx*h))

    bim.putpalette(palette)
    bim.save(filename, transparency=transparency)
