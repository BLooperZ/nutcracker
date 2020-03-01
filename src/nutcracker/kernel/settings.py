import logging
import struct
from dataclasses import dataclass, field

from typing import Mapping, Optional, Set

INCLUSIVE = 8
EXCLUSIVE = 0

UINT32BE = struct.Struct('>I')

@dataclass(frozen=True)
class _ChunkSetting:
    """Setting for resource chunks

    size_fix: int - can be used to determine whether size from chunk header
    is INCLUSIVE* (8) or EXCLUSIVE (0).

    * size of chunk header = 4CC tag (4) + word size (default 4) = 8 bytes

    align: int (default 2) - data alignment for chunk start offsets.

    word: struct.Struct (default UINT32BE) - Struct used to read chunk header size
    """
    size_fix: int = EXCLUSIVE
    align: int = 2
    word: struct.Struct = UINT32BE


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
    logger: logging.Logger = logging  # type: ignore
