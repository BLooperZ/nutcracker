import logging
import struct
from dataclasses import dataclass, field
from typing import Mapping, Optional, Set

from .structured import StructuredTuple
from .types import ChunkHeader

SCUMM_CHUNK = StructuredTuple(('size', 'tag'), struct.Struct('<I2s'), ChunkHeader)
IFF_CHUNK = StructuredTuple(('tag', 'size'), struct.Struct('>4sI'), ChunkHeader)

INCLUSIVE = IFF_CHUNK.size
EXCLUSIVE = 0


@dataclass(frozen=True)
class _ChunkSetting:
    """Setting for resource chunks

    size_fix: int -
        can be used to determine whether size from chunk header
        is INCLUSIVE* (8) or EXCLUSIVE (0).

    * size of chunk header = 4CC tag (4) + word size (default 4) = 8 bytes

    align: int (default 2) -
        data alignment for chunk start offsets.

    header: stream <-> ChunkHeader (default IFF_CHUNK) -
        structure to read/write chunk header
    """

    size_fix: int = EXCLUSIVE
    align: int = 2
    header: StructuredTuple[ChunkHeader] = IFF_CHUNK


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
