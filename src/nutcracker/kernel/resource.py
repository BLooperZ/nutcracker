#!/usr/bin/env python3

import io
from typing import IO, Iterator, Optional, Tuple

from .align import align_read_stream, align_write_stream
from .types import Chunk
from .settings import _ChunkSetting

def untag(cfg: _ChunkSetting, stream: IO[bytes]) -> Optional[Chunk]:
    """Read next chunk from given stream."""
    tag = stream.read(cfg.word.size)
    if not tag:
        return None
    if set(tag) != {0}:
        size = cfg.word.unpack(stream.read(cfg.word.size))[0] - cfg.size_fix
    else:
        # Collect rest of chunk as raw data with special tag '____'
        assert set(stream.read(cfg.word.size)) == {0}
        size = None
        tag = b'____'        
    data = stream.read(size)

    # verify data length
    if size and len(data) != size:
        raise EOFError(f'got EOF while reading chunk {str(tag)}: expected {size}, got {len(data)}')

    return Chunk(tag.decode(), data)

def read_chunks(cfg: _ChunkSetting, data: bytes) -> Iterator[Tuple[int, Chunk]]:
    """Read all chunks from given bytes."""
    max_size = len(data)
    with io.BytesIO(data) as stream:
        offset = stream.tell()
        assert offset == 0
        while offset < max_size:
            chunk = untag(cfg, stream)
            if not chunk:
                break
            yield offset, chunk
            align_read_stream(stream, align=cfg.align)
            offset = stream.tell()
        assert stream.read() == b''

def mktag(cfg: _ChunkSetting, tag: str, data: bytes) -> bytes:
    """Format chunk bytes from given 4CC tag and data."""
    # TODO: handle special '____' chunks
    return tag.encode() + cfg.word.pack(len(data) + cfg.size_fix) + data

def write_chunks_into(cfg: _ChunkSetting, stream: IO[bytes], chunks: Iterator[bytes]) -> None:
    """Write chunks sequence with given data alignment into given stream."""
    for chunk in chunks:
        assert chunk
        stream.write(chunk)
        align_write_stream(stream, align=cfg.align)

def write_chunks(cfg: _ChunkSetting, chunks: Iterator[bytes]) -> bytes:
    """Write chunks sequence to bytes with given data alignment."""
    with io.BytesIO() as stream:
        write_chunks_into(cfg, stream, chunks)
        return stream.getvalue()
