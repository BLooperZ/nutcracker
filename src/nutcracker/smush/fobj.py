#!/usr/bin/env python3

import io
import struct
from dataclasses import dataclass

from nutcracker.kernel.structured import StructuredTuple


@dataclass(frozen=True, order=True)
class FrameObjectHeader:
    codec: int
    x1: int
    y1: int
    x2: int
    y2: int
    unk1: int
    unk2: int


FOBJ_META = StructuredTuple(
    ('codec', 'x1', 'y1', 'x2', 'y2', 'unk1', 'unk2'),
    struct.Struct('<7H'),
    FrameObjectHeader,
)


@dataclass(frozen=True, order=True)
class FrameObject:
    header: FrameObjectHeader
    data: bytes


def unobj(data: bytes) -> FrameObject:
    with io.BytesIO(data) as stream:
        header = FOBJ_META.unpack(stream)
        return FrameObject(header, stream.read())


def mkobj(meta: FrameObjectHeader, data: bytes) -> bytes:
    return FOBJ_META.pack(meta) + data
