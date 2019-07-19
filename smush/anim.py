from . import smush, ahdr

from typing import cast, IO, Iterable, Iterator, Mapping, Tuple, TypeVar
from .smush_types import Chunk, AnimationHeader

T = TypeVar('T')

def verify_nframes(frames: Iterator[T], nframes: int) -> Iterator[T]:
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes:
            raise ValueError('too many frames')
        yield frame

def parse(stream: IO[bytes]) -> Tuple[AnimationHeader, Iterator[Iterator[Chunk]]]:
    anim = smush.assert_tag('ANIM', smush.untag(stream))
    assert stream.read() == b''

    anim_chunks = smush.read_chunks(anim, align=2)
    header = ahdr.from_bytes(smush.assert_tag('AHDR', next(anim_chunks)))

    frames = verify_nframes(
        (smush.assert_tag('FRME', frame) for frame in anim_chunks),
        header.nframes
    )

    chunked_frames = (smush.read_chunks(frame, align=2) for frame in frames)
    return header, chunked_frames
