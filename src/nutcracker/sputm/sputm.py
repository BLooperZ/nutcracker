#!/usr/bin/env python3

# NOTE: use function definition for typing information,
# until keyword/partial support is implemented in mypy.

import functools
from typing import IO, Iterator, Optional, Tuple  # ,Callable

from nutcracker.core import resource, index, chunk
from .types import Chunk
from .schema import SCHEMA

ALIGN = 1
SIZE_FIX = resource.INCLUSIVE

# untag: Callable[[IO[bytes]], Optional[Chunk]] = functools.partial(resource.untag, size_fix=SIZE_FIX)
@functools.wraps(resource.untag)
def untag(stream: IO[bytes], size_fix: int = SIZE_FIX) -> Optional[Chunk]:
    return resource.untag(stream, size_fix=size_fix)

# read_chunks: Callable[[bytes], Iterator[Chunk]] = functools.partial(resource.read_chunks, align=ALIGN)
@functools.wraps(resource.read_chunks)
def read_chunks(data: bytes, align: int = ALIGN, size_fix: int = SIZE_FIX) -> Iterator[Tuple[int, Chunk]]:
    return resource.read_chunks(data, align=align, size_fix=SIZE_FIX)

# untag: Callable[[str, bytes], bytes] = functools.partial(resource.mktag, size_fix=SIZE_FIX)
@functools.wraps(resource.mktag)
def mktag(tag: str, data: bytes, size_fix: int = SIZE_FIX) -> bytes:
    return resource.mktag(tag, data, size_fix=size_fix)

# untag: Callable[[Iterator[bytes]], bytes] = functools.partial(resource.write_chunks, align=ALIGN)
@functools.wraps(resource.write_chunks_bytes)
def write_chunks(chunks: Iterator[bytes], align: int = ALIGN) -> bytes:
    return resource.write_chunks_bytes(chunks, align=align)

@functools.wraps(index.map_chunks)
def map_chunks(data: IO[bytes], schema: dict = SCHEMA, ptag: Optional[str] = None, align: int = ALIGN, size_fix: int = SIZE_FIX, **kwargs):
    return index.map_chunks(data, schema=schema, align=align, size_fix=size_fix, **kwargs)

assert_tag = chunk.assert_tag
drop_offsets = chunk.drop_offsets
print_chunks = chunk.print_chunks

find = index.find
findall = index.findall
findpath = index.findpath
render = index.render
create_maptree = index.create_maptree
