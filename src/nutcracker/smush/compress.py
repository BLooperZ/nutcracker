from typing import Iterable, Iterator

from nutcracker.smush import anim
from nutcracker.smush.fobj import compress
from nutcracker.smush.preset import smush
from nutcracker.smush.types import Element


def compress_frame_data(frame: Element) -> Iterator[bytes]:
    first_fobj = True
    for comp in frame.children:
        if comp.tag == 'FOBJ' and first_fobj:
            first_fobj = False
            yield smush.mktag('ZFOB', compress(comp.data))
        elif comp.tag == 'PSAD':
            continue
            # print('skipping sound stream')
        else:
            first_fobj = first_fobj and comp.tag != 'ZFOB'
            yield smush.mktag(comp.tag, comp.data)


def compress_frames(frames: Iterable[Element]) -> Iterator[bytes]:
    yield from (
        smush.mktag('FRME', smush.write_chunks(compress_frame_data(frame)))
        for frame in frames
    )


def strip_compress_san(root: Element) -> bytes:
    header, frames = anim.parse(root)
    compressed_frames = compress_frames(frames)
    return anim.compose(header, compressed_frames)
