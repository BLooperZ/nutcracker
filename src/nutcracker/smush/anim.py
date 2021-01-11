import itertools
from typing import Iterator, Optional, Tuple

from nutcracker.smush import ahdr
from nutcracker.smush.preset import smush
from nutcracker.smush.types import Element
from nutcracker.smush.element import read_elements, read_data


def verify_nframes(frames: Iterator[Element], nframes: int) -> Iterator[Element]:
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes - 1:
            raise ValueError('too many frames')
        yield frame


def verify_maxframe(
    frames: Iterator[Element], limit: Optional[int]
) -> Iterator[Element]:
    maxframe = 0
    for elem in frames:
        maxframe = max(elem.attribs['size'], maxframe)
        yield elem
    if limit and maxframe > limit:
        raise ValueError(f'expected maxframe of {limit} but got {maxframe}')


def parse(root: Element) -> Tuple[ahdr.AnimationHeader, Iterator[Element]]:
    anim = read_elements('ANIM', root)
    header = ahdr.from_bytes(read_data('AHDR', next(anim)))

    frames = verify_nframes(verify_maxframe(anim, header.v2.maxframe), header.nframes)

    return header, frames


def compose(header: ahdr.AnimationHeader, frames: Iterator[bytes]) -> bytes:
    bheader = smush.mktag('AHDR', ahdr.to_bytes(header))
    return smush.mktag('ANIM', smush.write_chunks(itertools.chain([bheader], frames)))
