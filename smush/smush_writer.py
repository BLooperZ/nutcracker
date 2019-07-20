#!/usr/bin/env python3
import io
import struct

from . import smush

from functools import partial

from typing import Iterator, Tuple
from .smush_types import Chunk

def mktag(tag: str, data: bytes) -> bytes:
    return tag.encode() + struct.pack('>I', len(data)) + data

def write_chunks(chunks: Iterator[bytes], align: int = 2) -> bytes:
    with io.BytesIO() as stream:
        for chunk in chunks:
            pos = stream.tell()
            if pos % align != 0:
                stream.write(smush.calc_align(pos, align) * b'\00')
            stream.write(chunk)
        return stream.getvalue()
