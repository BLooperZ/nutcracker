#!/usr/bin/env python3

import struct
from dataclasses import dataclass, replace
from typing import Optional

from nutcracker.kernel.structured import StructuredTuple

PALETTE_SIZE = 0x300


@dataclass(frozen=True)
class AnimationHeaderV2:
    framerate: Optional[int] = None
    maxframe: Optional[int] = None
    samplerate: Optional[int] = None
    dummy2: Optional[int] = None
    dummy3: Optional[int] = None


@dataclass(frozen=True)
class AnimationHeader:
    version: int
    nframes: int
    dummy: int
    palette: bytes
    v2: AnimationHeaderV2 = AnimationHeaderV2()


AHDR_V1 = StructuredTuple(
    ('version', 'nframes', 'dummy', 'palette'),
    struct.Struct(f'<3H{PALETTE_SIZE}s'),
    AnimationHeader,
)

AHDR_V2 = StructuredTuple(
    ('framerate', 'maxframe', 'samplerate', 'dummy2', 'dummy3'),
    struct.Struct('<5I'),
    AnimationHeaderV2,
)


def from_bytes(data: bytes, offset: int = 0) -> AnimationHeader:
    header = AHDR_V1.unpack_from(data, offset)
    offset += AHDR_V1.size
    if header.version == 2:
        header = replace(header, v2=AHDR_V2.unpack_from(data, AHDR_V1.size))
        offset += AHDR_V2.size
    if len(data[offset:]) > 0:
        raise ValueError('got extra trailing data')
    if header.v2.dummy2 or header.v2.dummy3:
        raise ValueError('non-zero value in header dummies')
    return header


def to_bytes(header: AnimationHeader) -> bytes:
    return AHDR_V1.pack(header) + (
        AHDR_V2.pack(header.v2) if header.version == 2 else b''
    )
