#!/usr/bin/env python3

# NOTE: use function definition for typing information,
# until keyword/partial support is implemented in mypy.

import functools
# from functools import partial

import res.base
import res.chunk

from typing import IO, Iterator, Optional, Tuple  # ,Callable
from .smush_types import Chunk

ALIGN = 2
SIZE_FIX = res.base.EXCLUSIVE

# untag: Callable[[IO[bytes]], Optional[Chunk]] = partial(res.base.untag, size_fix=SIZE_FIX)
@functools.wraps(res.base.untag)
def untag(stream: IO[bytes], size_fix: int = SIZE_FIX) -> Optional[Chunk]:
    return res.base.untag(stream, size_fix=size_fix)

# read_chunks: Callable[[bytes], Iterator[Chunk]] = partial(res.base.read_chunks, align=ALIGN)
@functools.wraps(res.base.read_chunks)
def read_chunks(data: bytes, align: int = ALIGN, size_fix: int = SIZE_FIX) -> Iterator[Tuple[int, Chunk]]:
    return res.base.read_chunks(data, align=align, size_fix=size_fix)

# untag: Callable[[str, bytes], bytes] = partial(res.base.mktag, size_fix=SIZE_FIX)
@functools.wraps(res.base.mktag)
def mktag(tag: str, data: bytes, size_fix: int = SIZE_FIX) -> bytes:
    return res.base.mktag(tag, data, size_fix=size_fix)

# untag: Callable[[Iterator[bytes]], bytes] = partial(res.base.write_chunks, align=ALIGN)
@functools.wraps(res.base.write_chunks_bytes)
def write_chunks(chunks: Iterator[bytes], align: int = ALIGN) -> bytes:
    return res.base.write_chunks_bytes(chunks, align=align)

assert_tag = res.chunk.assert_tag
drop_offsets = res.chunk.drop_offsets
print_chunks = res.chunk.print_chunks
