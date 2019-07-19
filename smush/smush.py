#!/usr/bin/env python3

import io
import struct

import logging

from functools import partial

from typing import IO, Iterator, Optional, Tuple
from .smush_types import Chunk

def calc_align(pos: int, align: int):
    return (align - pos % align) % align

def align_stream(stream: IO[bytes], align: int = 1):
    pos = stream.tell()
    if pos % align == 0:
        return
    pad = stream.read(calc_align(pos, align))
    if pad and set(pad) != {0}:
        raise ValueError(f'non-zero padding between chunks: {pad}')

def untag(stream: IO[bytes]) -> Optional[Chunk]:
    tag = stream.read(4)
    if not tag:
        return None
    size = struct.unpack('>I', stream.read(4))[0]
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f'got EOF while reading chunk {tag}: expected {size}, got {len(data)}')
    return Chunk(tag.decode(), data)

def read_chunks(data: bytes, align: int = 2) -> Iterator[Chunk]:
    with io.BytesIO(data) as stream:
        for chunk in iter(partial(untag, stream), None):
            assert chunk
            align_stream(stream, align=align)
            yield chunk
        assert stream.read() == b''

def assert_tag(target: str, chunk: Optional[Chunk]) -> bytes:
    if not chunk:
        raise ValueError(f'no 4cc header')
    if chunk.tag != target:
        raise ValueError(f'expected tag to be {target} but got {chunk.tag}')
    return chunk.data
