#!/usr/bin/env python3

import io

from struct import Struct

PALETTE_SIZE = 256

primary_fields = ('version', 'nframes', 'unk1')
secondary_fields = ('secondary_version', 'unk2', 'sound_freq', 'zero1', 'zero2')
primary_struct = Struct('<{}H'.format(len(primary_fields)))
palette_struct = Struct('<{}B'.format(3 * PALETTE_SIZE))
secondary_struct = Struct('<{}I'.format(len(secondary_fields)))

def read_palette(strip):
    palette = palette_struct.unpack(strip)
    palette = list(zip(*[iter(palette)]*3)) #[palette[3*i:3*i+3] for i in range(256)]
    return palette

def parse_header(header):
    with io.BytesIO(header) as stream:
        primary = primary_struct.unpack(stream.read(primary_struct.size))
        primary = dict(zip(primary_fields, primary))
        primary['palette'] = read_palette(stream.read(palette_struct.size))

        secondary = {}
        if primary['version'] == 2:
            secondary = secondary_struct.unpack(stream.read(secondary_struct.size))
            secondary = dict(zip(secondary_fields, secondary))
        if stream.read():
            raise ValueError('got extra trailing data')
    
    return {**primary, **secondary}

