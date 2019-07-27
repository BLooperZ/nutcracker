#!/usr/bin/env python3

import io
import struct

from functools import partial

from .align import align_read_stream, align_write_stream

from typing import IO, Iterator, Optional
from .res_types import Chunk

def untag(stream: IO[bytes], size_fix: int = 0) -> Optional[Chunk]:
    """Read next chunk from given stream.

    size_fix: can be used to determine whether size from chunk header
    is inclusive* (8) or exclusive (0).

    * size of chunk header = 4CC tag (4) + uint32_be size (4) = 8 bytes
    """
    offset = stream.tell()
    tag = stream.read(4)
    if not tag:
        return None
    size = struct.unpack('>I', stream.read(4))[0] - size_fix
    print(offset, tag.decode(), size)
    # print(stream.tell(), tag, size)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f'got EOF while reading chunk {tag}: expected {size}, got {len(data)}')
    return Chunk(tag.decode(), data)

def read_chunks(data: bytes, align: int = 2) -> Iterator[Chunk]:
    """Read all chunks from given bytes.

    align: data alignment for chunk start offsets.
    """
    with io.BytesIO(data) as stream:
        for chunk in iter(partial(untag, stream), None):
            assert chunk
            align_read_stream(stream, align=align)
            yield chunk
        assert stream.read() == b''

def assert_tag(target: str, chunk: Optional[Chunk]) -> bytes:
    """Return chunk data if chunk has target 4CC tag."""
    if not chunk:
        raise ValueError(f'no 4cc header')
    if chunk.tag != target:
        raise ValueError(f'expected tag to be {target} but got {chunk.tag}')
    return chunk.data

def mktag(tag: str, data: bytes, size_fix: int = 0) -> bytes:
    """Format chunk bytes from given 4CC tag and data.

    size_fix: can be used to determine whether size from chunk header
    is inclusive* (8) or exclusive (0).

    * size of chunk header = 4CC tag (4) + uint32_be size (4) = 8 bytes
    """
    return tag.encode() + struct.pack('>I', len(data) + size_fix) + data

def write_chunks(stream: IO[bytes], chunks: Iterator[bytes], align: int = 2) -> None:
    """Write chunks sequence with given data alignment into given stream.

    align: data alignment for chunk start offsets.
    """
    for chunk in chunks:
        assert chunk
        stream.write(chunk)
        align_write_stream(stream, align=align)
        # print(stream.tell(), chunk[:4])

def write_chunks_bytes(chunks: Iterator[bytes], align: int = 2) -> bytes:
    """Write chunks sequence to bytes with given data alignment.

    align: data alignment for chunk start offsets.
    """
    with io.BytesIO() as stream:
        write_chunks(stream, chunks, align=align)
        return stream.getvalue()
