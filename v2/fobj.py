#!/usr/bin/env python3

import io
from struct import Struct

meta_fields = ('codec', 'x1', 'y1', 'x2', 'y2', 'unk1', 'unk2')
meta_struct = Struct('<{}H'.format(len(meta_fields)))

def unobj(data):
    meta = meta_struct.unpack(data[:meta_struct.size])
    meta = dict(zip(meta_fields, meta))
    data = data[meta_struct.size:]
    return meta, data

def mkobj(meta, data):
    metas = (v for k, v in meta.items())
    return meta_struct.pack(*metas) + data

