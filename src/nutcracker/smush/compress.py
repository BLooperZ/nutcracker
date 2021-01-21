#!/usr/bin/env python3

from typing import Iterable, Iterator

from nutcracker.smush import anim
from nutcracker.smush.types import Element
from nutcracker.smush.preset import smush
from nutcracker.smush.fobj import compress


def compress_frame_data(frame: Element) -> Iterator[bytes]:
    first_fobj = True
    for comp in frame.children:
        if comp.tag == 'FOBJ' and first_fobj:
            first_fobj = False
            yield smush.mktag('ZFOB', compress(comp.data))
            continue
        if comp.tag == 'PSAD':
            # print('skipping sound stream')
            continue
        else:
            first_fobj = first_fobj and comp.tag != 'ZFOB'
            yield smush.mktag(comp.tag, comp.data)
            continue


def compress_frames(frames: Iterable[Element]) -> Iterator[bytes]:
    for frame in frames:
        yield smush.mktag('FRME', smush.write_chunks(compress_frame_data(frame)))


def strip_compress_san(root: Element) -> bytes:
    header, frames = anim.parse(root)
    compressed_frames = compress_frames(frames)
    return anim.compose(header, compressed_frames)
