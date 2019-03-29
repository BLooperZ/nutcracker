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

    locs, frames = zip(*frames)
    im_frames = (convert_to_pil_image(frame) for frame in frames)

    get_bg = get_bg_color(1, lambda idx: idx)

    stack = (resize_pil_image(w, h, get_bg(idx), frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs)))

    num_frames = len(frames)
    enpp = np.array([[transparency] * w] * h * num_frames, dtype=np.uint8)
    bim = Image.fromarray(enpp, mode='P')

    for idx, frame in enumerate(stack):
        bim.paste(frame, box=(0, idx*h))

    bim.putpalette(palette)
    bim.save(filename, transparency=transparency)

def save_image_grid(filename, frames, palette, transparency=None):
    w = 32
    h = 48
    grid_size = 16

    palette = [x for l in palette for x in l]

    locs, frames = zip(*frames)
    im_frames = (convert_to_pil_image(frame) for frame in frames)

    get_bg = get_bg_color(grid_size, lambda idx: idx + int(idx / grid_size))

    stack = (resize_pil_image(w, h, get_bg(idx), frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs)))

    enpp = np.array([[transparency] * w * grid_size] * h * grid_size, dtype=np.uint8)
    bim = Image.fromarray(enpp, mode='P')

    for idx, frame in enumerate(stack):
        bim.paste(frame, box=((idx % grid_size) * w, int(idx / grid_size) * h))

    palette[39*3] = 109
    palette[39*3+1] = 109
    palette[39*3+1] = 109
    bim.putpalette(palette)
    bim.save(filename) #, transparency=transparency)

def save_frame_image(frames, palette, transparency=None):
    palette = [x for l in palette for x in l]

    locs, frames = zip(*frames)
    im_frames = (convert_to_pil_image(frame) for frame in frames)

    get_bg = get_bg_color(1, lambda idx: idx + int(idx))

    locs = list(locs)
    for loc in locs:
        print(f"x1: {loc['x1']}, x2: {loc['x2']}")
    w = max(loc['x1'] + loc['x2'] for loc in locs)
    h = max(loc['y1'] + loc['y2'] for loc in locs)

    stack = (resize_pil_image(w, h, get_bg(idx), frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs)))

    palette[39*3] = 109
    palette[39*3+1] = 109
    palette[39*3+1] = 109
    for frame in stack:
        frame.putpalette(palette)
        yield frame
