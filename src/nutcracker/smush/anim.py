import itertools

from . import smush, ahdr

from typing import cast, IO, Iterable, Iterator, Mapping, Tuple, TypeVar
from .smush_types import Chunk, AnimationHeader

T = TypeVar('T')

def verify_nframes(frames: Iterator[T], nframes: int) -> Iterator[T]:
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes:
            raise ValueError('too many frames')
        yield frame

def print_maxframe(frames: Iterator[Tuple[int, Chunk]]) -> Iterator[Tuple[int, Chunk]]:
    maxframe = 0
    last_chunk = None
    for offset, chunk in frames:
        if last_chunk:
            maxframe = max(maxframe, offset - last_offset)
            assert offset - last_offset == 8 + len(last_chunk.data), \
                (offset - last_offset, 8 + len(last_chunk.data))
        last_offset = offset
        last_chunk = chunk
        yield offset, chunk
    print(f'maxframe: {maxframe + 1}')

def parse(stream: IO[bytes]) -> Tuple[AnimationHeader, Iterator[Iterator[Tuple[int, Chunk]]]]:
    anim = smush.assert_tag('ANIM', smush.untag(stream))
    assert stream.read() == b''

    anim_chunks = smush.print_chunks(smush.read_chunks(anim, align=2))
    header = ahdr.from_bytes(smush.assert_tag('AHDR', next(chunk for _, chunk in anim_chunks)))
    assert not (header.dummy2 or header.dummy3)

    print(header)

    anim_chunks = print_maxframe(anim_chunks)

    frames = verify_nframes(
        (smush.assert_tag('FRME', frame) for _, frame in anim_chunks),
        header.nframes
    )

    chunked_frames = (smush.read_chunks(frame, align=2) for frame in frames)

    return header, chunked_frames

def compose(header: AnimationHeader, frames: Iterator[bytes]):
    bheader = smush.mktag('AHDR', ahdr.to_bytes(header))
    return smush.mktag(
        'ANIM',
        smush.write_chunks(
            itertools.chain([bheader], frames),
            align=2
        )
    )
