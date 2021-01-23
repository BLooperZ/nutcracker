import itertools
from typing import Any, Dict, Iterator, NamedTuple, Optional

from nutcracker.kernel.types import Chunk
from nutcracker.utils.fileio import read_file
from nutcracker.smush import ahdr
from nutcracker.smush.preset import smush
from nutcracker.smush.types import Element
from nutcracker.smush.element import read_elements, read_data


class SmushAnimation(NamedTuple):
    header: ahdr.AnimationHeader
    frames: Iterator[Element]


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


def parse(root: Element) -> SmushAnimation:
    anim = read_elements('ANIM', root)
    header = ahdr.from_bytes(read_data('AHDR', next(anim)))

    frames = verify_nframes(verify_maxframe(anim, header.v2.maxframe), header.nframes)

    return SmushAnimation(header, frames)


def compose(header: ahdr.AnimationHeader, frames: Iterator[bytes]) -> bytes:
    bheader = smush.mktag('AHDR', ahdr.to_bytes(header))
    return smush.mktag('ANIM', smush.write_chunks(itertools.chain([bheader], frames)))


def from_bytes(resource: bytes) -> Element:
    it = itertools.count()

    def set_frame_id(
        parent: Optional[Element], chunk: Chunk, offset: int
    ) -> Dict[str, Any]:
        if chunk.tag != 'FRME':
            return {}
        return {'id': next(it)}

    return next(smush.map_chunks(resource, extra=set_frame_id))


def from_path(path: str) -> Element:
    return from_bytes(read_file(path))
