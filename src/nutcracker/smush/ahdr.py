#!/usr/bin/env python3

import io
from functools import partial
from struct import Struct
from typing import Mapping, Sequence, Union

from . import structure
from .types import AnimationHeader

PALETTE_SIZE = 3 * 256

primary_fields = ('version', 'nframes', 'dummy')
secondary_fields = ('framerate', 'maxframe', 'samplerate', 'dummy2', 'dummy3')
primary_struct = Struct(f'<{len(primary_fields)}H')
secondary_struct = Struct(f'<{len(secondary_fields)}I')

read_primary = partial(structure.read, primary_fields, primary_struct)
read_secondary = partial(structure.read, secondary_fields, secondary_struct)

def from_bytes(header: bytes) -> AnimationHeader:
    with io.BytesIO(header) as stream:
        primary = read_primary(stream)
        palette = tuple(stream.read(PALETTE_SIZE))
        secondary = read_secondary(stream) if primary['version'] == 2 else {}
        if stream.read():
            raise ValueError('got extra trailing data')
    return AnimationHeader(
        version=primary['version'],
        nframes=primary['nframes'],
        dummy=primary['dummy'],
        palette=palette,
        framerate=secondary.get('framerate', None),
        maxframe=secondary.get('maxframe', None),
        samplerate=secondary.get('samplerate', None),
        dummy2=secondary.get('dummy2', None),
        dummy3=secondary.get('dummy3', None)
    )

def to_bytes(header: AnimationHeader) -> bytes:
    base = primary_struct.pack(*header[:3]) + bytes(header.palette)
    if header.version == 2:
        return base + secondary_struct.pack(*header[4:])
    return base

def create(base: AnimationHeader, **kwargs):
    return base._replace(**kwargs)
