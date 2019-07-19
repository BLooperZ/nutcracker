#!/usr/bin/env python3

import io

from functools import partial
from struct import Struct

from . import structure

from typing import Mapping, Sequence, Union

from .smush_types import AnimationHeader

PALETTE_SIZE = 3 * 256

primary_fields = ('version', 'nframes', 'unk1')
secondary_fields = ('secondary_version', 'unk2', 'sound_freq', 'zero1', 'zero2')
primary_struct = Struct('<{}H'.format(len(primary_fields)))
secondary_struct = Struct('<{}I'.format(len(secondary_fields)))

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
        unk1=primary['unk1'],
        palette=palette,
        secondary_version=secondary.get('secondary_version', None),
        unk2=secondary.get('unk2', None),
        sound_freq=secondary.get('sound_freq', None),
        zero1=secondary.get('zero1', None),
        zero2=secondary.get('zero2', None)
    )

def to_bytes(header: AnimationHeader) -> bytes:
    base = primary_struct.pack(*header[:3]) + bytes(header.palette)
    if header.version == 2:
        return base + secondary_struct.pack(*header[4:])
    return base

def create(base: AnimationHeader, **kwargs):
    return AnimationHeader(
        version=kwargs.get('version', base.version),
        nframes=kwargs.get('nframes', base.nframes),
        unk1=kwargs.get('unk1', base.unk1),
        palette=kwargs.get('palette', base.palette),
        secondary_version=kwargs.get('secondary_version', base.secondary_version),
        unk2=kwargs.get('unk2', base.unk2),
        sound_freq=kwargs.get('sound_freq', base.sound_freq),
        zero1=kwargs.get('zero1', base.zero1),
        zero2=kwargs.get('zero2', base.zero2)
    )
