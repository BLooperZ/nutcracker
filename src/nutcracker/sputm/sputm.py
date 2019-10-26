#!/usr/bin/env python3

# NOTE: use function definition for typing information,
# until keyword/partial support is implemented in mypy.

import functools
from typing import IO, Iterator, Optional, Tuple  # ,Callable

from nutcracker.res import base, chunk

from .sputm_types import Chunk

ALIGN = 1
SIZE_FIX = base.INCLUSIVE

# untag: Callable[[IO[bytes]], Optional[Chunk]] = functools.partial(base.untag, size_fix=SIZE_FIX)
@functools.wraps(base.untag)
def untag(stream: IO[bytes], size_fix: int = SIZE_FIX) -> Optional[Chunk]:
    return base.untag(stream, size_fix=size_fix)

# read_chunks: Callable[[bytes], Iterator[Chunk]] = functools.partial(base.read_chunks, align=ALIGN)
@functools.wraps(base.read_chunks)
def read_chunks(data: bytes, align: int = ALIGN, size_fix: int = SIZE_FIX) -> Iterator[Tuple[int, Chunk]]:
    return base.read_chunks(data, align=align, size_fix=SIZE_FIX)

# untag: Callable[[str, bytes], bytes] = functools.partial(base.mktag, size_fix=SIZE_FIX)
@functools.wraps(base.mktag)
def mktag(tag: str, data: bytes, size_fix: int = SIZE_FIX) -> bytes:
    return base.mktag(tag, data, size_fix=size_fix)

# untag: Callable[[Iterator[bytes]], bytes] = functools.partial(base.write_chunks, align=ALIGN)
@functools.wraps(base.write_chunks_bytes)
def write_chunks(chunks: Iterator[bytes], align: int = ALIGN) -> bytes:
    return base.write_chunks_bytes(chunks, align=align)

assert_tag = chunk.assert_tag
drop_offsets = chunk.drop_offsets
print_chunks = chunk.print_chunks
