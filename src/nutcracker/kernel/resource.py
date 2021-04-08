import logging
from typing import Iterable, Iterator, Tuple, Union

from .align import align_read, align_write
from .buffer import BufferLike
from .chunk import Chunk
from .settings import _ChunkSetting


def read_chunks(
    cfg: _ChunkSetting, buffer: BufferLike, offset: int = 0
) -> Iterator[Tuple[int, Chunk]]:
    """Read all chunks from given bytes."""
    data = memoryview(buffer)
    max_size = len(data)
    while offset < max_size:
        offset = workaround_x80(cfg, buffer, offset)
        chunk = cfg.untag(data, offset)
        yield offset, chunk
        offset = align_read(data, offset + len(chunk), align=cfg.align)
    assert offset == max_size


def workaround_x80(cfg: _ChunkSetting, buffer: BufferLike, offset: int = 0) -> int:
    """WORKAROUND: in Pajama Sam 2, some DIGI chunks are off by 1.
    header appears as '\\x80DIG' and index indicate they should start 1 byte afterwards.
    since header tag needs to be ASCII, it's low risk.
    """
    if buffer[offset] == 0x80:
        getattr(cfg, 'logger', logging).warning(
            'found \\x80 between chunks, skipping 1 byte...'
        )
        return offset + 1
    return offset



def write_chunks(cfg: _ChunkSetting, chunks: Iterable[Union[bytes, Chunk]]) -> bytes:
    """Write chunks sequence to bytes with given data alignment."""
    stream = bytearray()
    for chunk in chunks:
        assert chunk
        stream += align_write(bytes(chunk), align=cfg.align)
    return bytes(stream)
