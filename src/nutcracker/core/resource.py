#!/usr/bin/env python3

import io
import itertools
import struct
from functools import partial
from typing import IO, Iterator, Optional, Tuple

from .align import align_read_stream, align_write_stream
from .types import Chunk
from .stream import StreamView, Stream

INCLUSIVE = 8
EXCLUSIVE = 0

def stream_size(stream: Stream) -> int:
    pos = stream.tell()
    stream.read()
    size = stream.tell()
    stream.seek(pos, io.SEEK_SET)
    return size

def untag(stream: IO[bytes], size_fix: int = EXCLUSIVE) -> Optional[Chunk]:
    """Read next chunk from given stream.

    size_fix: can be used to determine whether size from chunk header
    is INCLUSIVE* (8) or EXCLUSIVE (0).

    * size of chunk header = 4CC tag (4) + uint32_be size (4) = 8 bytes
    """
    tag = stream.read(4)
    if not tag:
        return None
    size = struct.unpack('>I', stream.read(4))[0] - size_fix
    data = StreamView(stream, size)

    # verify stream size
    actual = stream_size(data)
    if actual != size:
        raise ValueError(f'got EOF while reading chunk {tag}: expected {size}, got {actual}')

    return Chunk(tag.decode(), data)

def read_chunks(stream: IO[bytes], align: int = 2, size_fix: int = EXCLUSIVE) -> Iterator[Tuple[int, Chunk]]:
    """Read all chunks from given bytes.

    align: data alignment for chunk start offsets.
    """
    offsets = iter(stream.tell, stream_size(stream))
    chunks = iter(partial(untag, stream, size_fix=size_fix), None)
    for offset, chunk in zip(offsets, chunks):
        assert chunk
        yield offset, chunk
        align_read_stream(stream, align=align)
    assert stream.read() == b''
    assert not list(itertools.zip_longest(chunks, offsets))

def mktag(tag: str, data: bytes, size_fix: int = EXCLUSIVE) -> bytes:
    """Format chunk bytes from given 4CC tag and data.

    size_fix: can be used to determine whether size from chunk header
    is INCLUSIVE* (8) or EXCLUSIVE (0).

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

def write_chunks_bytes(chunks: Iterator[bytes], align: int = 2) -> bytes:
    """Write chunks sequence to bytes with given data alignment.

    align: data alignment for chunk start offsets.
    """
    with io.BytesIO() as stream:
        write_chunks(stream, chunks, align=align)
        return stream.getvalue()
