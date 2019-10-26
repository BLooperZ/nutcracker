#!/usr/bin/env python3

import io

from functools import partial
from struct import Struct
from typing import Mapping, Tuple

from . import structure

meta_fields = ('codec', 'x1', 'y1', 'x2', 'y2', 'unk1', 'unk2')
meta_struct = Struct('<{}H'.format(len(meta_fields)))

read_meta = partial(structure.read, meta_fields, meta_struct)

def unobj(data: bytes) -> Tuple[Mapping[str, int], bytes]:
    meta = dict(zip(
        meta_fields,
        meta_struct.unpack(data[:meta_struct.size])
    ))
    data = data[meta_struct.size:]
    return meta, data

def mkobj(meta, data):
    metas = meta.values()
    return meta_struct.pack(*metas) + data
