import logging
from dataclasses import dataclass, field
from struct import Struct
from typing import Mapping, Optional, Set

from .buffer import BufferLike
from .chunk import Chunk, ChunkFactory, ChunkHeader, SizeFixedChunk, StructuredChunk
from .structured import StructuredTuple

SCUMM_CHUNK_HEADER = StructuredTuple(('size', 'etag'), Struct('<I2s'), ChunkHeader)
IFF_CHUNK_HEADER = StructuredTuple(('etag', 'size'), Struct('>4sI'), ChunkHeader)

SCUMM_CHUNK = StructuredChunk(SCUMM_CHUNK_HEADER)
IFF_CHUNK_IN = SizeFixedChunk(IFF_CHUNK_HEADER)
IFF_CHUNK_EX = SizeFixedChunk(IFF_CHUNK_HEADER, size_fix=IFF_CHUNK_HEADER.size)


@dataclass(frozen=True)
class _ChunkSetting(ChunkFactory):
    """Setting for resource chunks

    align: int (default 2) -
        data alignment for chunk start offsets.

    chunk: stream <-> Chunk (default IFF_CHUNK_EX) -
        factory to read/write chunk header
    """

    align: int = 2
    chunk: ChunkFactory = IFF_CHUNK_EX

    def untag(self, buffer: BufferLike, offset: int = 0) -> Chunk:
        """Read chunk from given buffer."""
        return self.chunk.untag(buffer, offset=offset)

    def mktag(self, tag: str, data: bytes) -> bytes:
        """Create chunk bytes from given tag and data."""
        return self.chunk.mktag(tag, data)


@dataclass(frozen=True)
class _IndexSetting(_ChunkSetting):
    """Setting for indexing chunk resources

    contains all fields from _ChunkSetting, and the following:

    schema: mapping of containers tags to set of child tags

    strict: if set to True, throws error on schema mismatch, otherwise log warning

    max_depth: limit levels of container chunks to index, None for unlimited
    """

    schema: Mapping[str, Set[str]] = field(default_factory=dict)
    strict: bool = False
    max_depth: Optional[int] = None
    logger: logging.Logger = logging.root
