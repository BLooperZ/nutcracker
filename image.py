#!/usr/bin/env python3

from PIL import Image
import numpy as np
from operator import itemgetter

def get_bg_color(row_size, f):
    BGS = [5, 4]

    def get_bg(idx):
        return BGS[f(idx) % len(BGS)]
    return get_bg

def convert_to_pil_image(frame):
    try:
        npp = np.array(frame, dtype=np.uint8)
        im = Image.fromarray(npp, mode='P')
        return im
    except Exception as e:
        print(frame)

def resize_pil_image(w, h, bg, im, loc):
    nbase = convert_to_pil_image([[bg] * w] * h)
    # nbase.paste(im, box=itemgetter('x1', 'y1', 'x2', 'y2')(loc))
    nbase.paste(im, box=itemgetter('x1', 'y1')(loc))
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
    base_xoff = 8
    base_yoff = 8
    w = 48 + base_xoff
    h = 48 + base_yoff
    grid_size = 16

    palette = list(palette)

    locs, frames = zip(*frames)
    im_frames = (convert_to_pil_image(frame) for frame in frames)

    get_bg = get_bg_color(grid_size, lambda idx: idx + int(idx / grid_size))

    # stack = (resize_pil_image(w, h, get_bg(idx), frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs)))

    enpp = np.array([[transparency] * w * grid_size] * h * grid_size, dtype=np.uint8)
    bim = Image.fromarray(enpp, mode='P')

    stack = list(im_frames)
    nchars = len(stack)

    for i in range(nchars):
        ph = convert_to_pil_image([[get_bg(i)] * w] * h)
        bim.paste(ph, box=((i % grid_size) * w, int(i / grid_size) * h))

    for idx, (frame, loc) in enumerate(zip(stack, locs)):
        bim.paste(frame, box=((idx % grid_size) * w + base_xoff + loc['x1'], int(idx / grid_size) * h + base_yoff + loc['y1']))

    palette[3 * transparency: 3 * transparency + 3] = [109, 109, 109]
    bim.putpalette(palette)
    bim.save(filename) #, transparency=transparency)

def save_frame_image(frames):

    locs, frames = zip(*frames)
    im_frames = (convert_to_pil_image(frame) for frame in frames)

    get_bg = get_bg_color(1, lambda idx: idx + int(idx))

    locs = list(locs)
    for idx, loc in enumerate(locs):
        print(f"FRAME {idx} - x1: {loc['x1']}, x2: {loc['x2']}")

    w = max(loc['x1'] + loc['x2'] for loc in locs)
    h = max(loc['y1'] + loc['y2'] for loc in locs)

    w = next(loc['x1'] + loc['x2'] for loc in locs)
    h = next(loc['y1'] + loc['y2'] for loc in locs)
    print((w, h))

    stack = (resize_pil_image(w, h, get_bg(idx), frame, loc) for idx, (frame, loc) in enumerate(zip(im_frames, locs)))

    for frame in stack:
        yield frame

def save_single_frame_image(frame, resize=None):

    loc, frame = frame
    if not resize:
        return convert_to_pil_image(frame)

    idx = 0
    get_bg = get_bg_color(1, lambda idx: idx + int(idx))

    w, h = resize

    # w = loc['x1'] + loc['x2']
    # h = loc['y1'] + loc['y2']

    # w = 320
    # h = 200

    return resize_pil_image(w, h, get_bg(idx), frame, loc)
