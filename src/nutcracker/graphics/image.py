from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence, Tuple, Union

import numpy as np
from PIL import Image

Box = Union[Tuple[int, ...]]
Matrix = Sequence[Sequence[int]]


class TImage(Protocol):
    def paste(
        self,
        im: Union['TImage', Matrix],
        box: Optional[Box] = None,
        mask: Optional['TImage'] = None,
    ) -> None:
        ...

    def crop(self, box: Box) -> 'TImage':
        ...

    def putpalette(self, data: Sequence[int], rawmode: str = 'RGB') -> None:
        ...

    def save(self, fp: str, format: Optional[str] = None, **params: Any) -> None:
        ...


@dataclass
class ImagePosition:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0


def convert_to_pil_image(
    char: Sequence[Sequence[int]], size: Optional[Tuple[int, int]] = None
) -> TImage:
    # print('CHAR:', char)
    npp = np.array(list(char), dtype=np.uint8)
    if size:
        width, height = size
        npp.resize(height, width)
    im = Image.fromarray(npp, mode='P')
    return im
