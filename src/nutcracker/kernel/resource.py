#!/usr/bin/env python3

import io
import logging
from typing import IO, Iterable, Iterator, Optional, Tuple

from .align import align_read_stream, align_write_stream
from .settings import _ChunkSetting
from .types import Chunk, ChunkHeader


class UnexpectedBufferSize(EOFError):
    def __init__(self, expected: int, given: int) -> None:
        super().__init__(f'Expected buffer of size {expected} but got size {given}')
        self.expected = expected
        self.given = given


def validate_buffer_size(data: bytes, size: Optional[int] = None) -> bytes:
    if size and len(data) != size:
        raise UnexpectedBufferSize(size, len(data))
    return data


def strict_read(stream: IO[bytes], size: Optional[int] = None) -> bytes:
    return validate_buffer_size(stream.read(size), size)  # type: ignore


def untag(cfg: _ChunkSetting, stream: IO[bytes]) -> Chunk:
    """Read next chunk from given stream."""
    header = cfg.header.unpack(stream)
    if set(header.tag) == {0} and header.size == 0:
        # Collect rest of chunk as raw data with special tag '____'
        return Chunk('____', strict_read(stream))
    size = header.size - cfg.size_fix
    return Chunk(header.tag.decode(), strict_read(stream, size))


def read_chunks(cfg: _ChunkSetting, data: bytes) -> Iterator[Tuple[int, Chunk]]:
    """Read all chunks from given bytes."""
    max_size = len(data)
    with io.BytesIO(data) as stream:
        offset = stream.tell()
        assert offset == 0
        while offset < max_size:
            offset = workaround_x80(cfg, stream)  # workaround, see docstring
            chunk = untag(cfg, stream)
            yield offset, chunk
            offset = align_read_stream(stream, align=cfg.align)
            assert offset == stream.tell()
        assert stream.read() == b''


def workaround_x80(cfg: _ChunkSetting, stream: IO[bytes]) -> int:
    """WORKAROUND: in Pajama Sam 2, some DIGI chunks are off by 1.
    header appears as '\\x80DIG' and index indicate they should start 1 byte afterwards.
    since header tag needs to be ASCII, it's low risk.
    """
    if stream.read(1) == b'\x80':
        getattr(cfg, 'logger', logging).warning(
            'found \\x80 between chunks, skipping 1 byte...'
        )
        return stream.tell()
    return stream.seek(-1, io.SEEK_CUR)


def mktag(cfg: _ChunkSetting, tag: str, data: bytes) -> bytes:
    """Format chunk bytes from given 4CC tag and data."""
    # handle special '____' chunks
    if tag == '____':
        return cfg.header.pack(ChunkHeader(b'', 0)) + data
    return cfg.header.pack(ChunkHeader(tag.encode(), len(data) + cfg.size_fix)) + data


def write_chunks_into(
    cfg: _ChunkSetting, stream: IO[bytes], chunks: Iterable[bytes]
) -> None:
    """Write chunks sequence with given data alignment into given stream."""
    for chunk in chunks:
        assert chunk
        stream.write(chunk)
        align_write_stream(stream, align=cfg.align)


def write_chunks(cfg: _ChunkSetting, chunks: Iterable[bytes]) -> bytes:
    """Write chunks sequence to bytes with given data alignment."""
    with io.BytesIO() as stream:
        write_chunks_into(cfg, stream, chunks)
        return stream.getvalue()
