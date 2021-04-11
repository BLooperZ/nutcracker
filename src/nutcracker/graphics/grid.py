import itertools
from typing import (
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    cast,
)

import numpy as np
from PIL import Image

from nutcracker.graphics.image import ImagePosition, TImage, convert_to_pil_image
from nutcracker.utils import funcutils

T = TypeVar('T')


BGS = [b'0', b'n']
BASE_XOFF = 8
BASE_YOFF = 8
TILE_W = 48 + BASE_XOFF
TILE_H = 48 + BASE_YOFF
GRID_SIZE = 16


def get_bg_color(
    row_size: int, f: Callable[[int], int], bgs: Sequence[bytes] = BGS
) -> Callable[[int], int]:
    def get_bg(idx: int) -> int:
        return ord(bgs[f(idx) % len(bgs)])

    return get_bg


def read_image_grid(
    filename: str, w: int = TILE_W, h: int = TILE_H, grid_size: int = GRID_SIZE
) -> Iterator[TImage]:
    bim = Image.open(filename)

    for row in range(grid_size):
        for col in range(grid_size):
            area = (col * w, row * h, (col + 1) * w, (row + 1) * h)
            yield bim.crop(area)


def checkered_grid(
    nchars: int,
    w: int = TILE_W,
    h: int = TILE_H,
    grid_size: int = GRID_SIZE,
    transparency: int = 0,
    bgs: Sequence[bytes] = BGS,
) -> TImage:
    assert nchars <= grid_size ** 2, nchars

    bim = convert_to_pil_image([[transparency] * w * grid_size] * h * grid_size)
    get_bg = get_bg_color(grid_size, lambda idx: idx + int(idx / grid_size), bgs=bgs)

    # nchars does not have to match real number of characters nor max. index
    for i in range(nchars):
        ph = convert_to_pil_image([[get_bg(i)] * w] * h)
        bim.paste(ph, box=((i % grid_size) * w, int(i / grid_size) * h))

    return bim


def create_char_grid(
    nchars: int,
    chars: Iterable[Tuple[int, Tuple[int, int, TImage]]],
    w: int = TILE_W,
    h: int = TILE_H,
    grid_size: int = GRID_SIZE,
    base_xoff: int = BASE_XOFF,
    base_yoff: int = BASE_YOFF,
    transparency: int = 0,
    bgs: Sequence[bytes] = BGS,
) -> TImage:
    bim = checkered_grid(
        nchars, w=w, h=h, grid_size=grid_size, transparency=transparency, bgs=bgs
    )

    # idx is character index in ascii table
    for idx, (xoff, yoff, im) in chars:
        assert idx < nchars
        xbase = (idx % grid_size) * w + base_xoff
        ybase = (idx // grid_size) * h + base_yoff
        bim.paste(im, box=(xbase + xoff, ybase + yoff))

    return bim


def count_in_row(pred: Callable[[T], bool], row: Iterable[T]) -> int:
    return sum(1 for _ in itertools.takewhile(pred, row))


def resize_frame(
    im: TImage, base_xoff: int = BASE_XOFF, base_yoff: int = BASE_YOFF
) -> Optional[Tuple[ImagePosition, np.ndarray]]:
    frame = list(np.asarray(im))
    BG = cast(int, frame[-1][-1])

    def char_is_bg(c: int) -> bool:
        return c == BG

    def line_is_bg(line: List[int]) -> bool:
        return all(char_is_bg(c) for c in line)

    if set(funcutils.flatten(frame)) == {BG}:
        return None

    x1 = min(count_in_row(char_is_bg, line) for line in frame)
    x2 = len(frame[0]) - min(count_in_row(char_is_bg, reversed(line)) for line in frame)
    y1 = count_in_row(line_is_bg, frame)
    y2 = len(frame) - count_in_row(line_is_bg, reversed(frame))

    crop_area = (x1, y1, x2, y2)

    if crop_area == (0, 0, len(frame[0]), len(frame)):
        return None

    loc = ImagePosition(
        x1=x1 - base_xoff, y1=y1 - base_yoff, x2=x2 - base_xoff, y2=y2 - base_yoff
    )

    return loc, np.asarray(im.crop(crop_area))
