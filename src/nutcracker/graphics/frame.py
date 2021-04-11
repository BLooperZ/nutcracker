#!/usr/bin/env python3
from operator import attrgetter
from typing import Iterator, Optional, Sequence, Tuple, Union

from nutcracker.graphics.grid import get_bg_color
from nutcracker.graphics.image import (
    ImagePosition,
    Matrix,
    TImage,
    convert_to_pil_image,
)

BGS = [b'\05', b'\04']


def resize_pil_image(
    w: int,
    h: int,
    bg: int,
    im: Union[TImage, Matrix],
    loc: ImagePosition,
) -> TImage:
    nbase = convert_to_pil_image([[bg] * w] * h)
    # nbase.paste(im, box=itemgetter('x1', 'y1', 'x2', 'y2')(loc))
    nbase.paste(im, box=attrgetter('x1', 'y1')(loc))
    return nbase


def save_frame_image(
    frames: Sequence[Tuple[ImagePosition, TImage]]
) -> Iterator[TImage]:

    rlocs, frames = zip(*frames)
    im_frames = (convert_to_pil_image(frame) for frame in frames)

    get_bg = get_bg_color(1, lambda idx: idx + int(idx), bgs=BGS)

    locs = list(rlocs)
    for idx, loc in enumerate(locs):
        print(f"FRAME {idx} - x1: {loc['x1']}, x2: {loc['x2']}")

    w = max(loc['x1'] + loc['x2'] for loc in locs)
    h = max(loc['y1'] + loc['y2'] for loc in locs)

    w = next(loc['x1'] + loc['x2'] for loc in locs)
    h = next(loc['y1'] + loc['y2'] for loc in locs)
    print((w, h))

    stack = (
        resize_pil_image(w, h, get_bg(idx), frame, loc)
        for idx, (frame, loc) in enumerate(zip(im_frames, locs))
    )

    for frame in stack:
        yield frame


def save_single_frame_image(
    frame: Tuple[ImagePosition, Matrix],
    resize: Optional[Tuple[int, int]] = None,
) -> TImage:

    loc, frame_data = frame
    if not resize:
        return convert_to_pil_image(frame_data)

    idx = 0
    get_bg = get_bg_color(1, lambda idx: idx + int(idx), bgs=BGS)

    w, h = resize

    # w = loc['x1'] + loc['x2']
    # h = loc['y1'] + loc['y2']

    # w = 320
    # h = 200

    return resize_pil_image(w, h, get_bg(idx), frame_data, loc)
