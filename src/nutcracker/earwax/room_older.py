
import glob
import io
import os
import pathlib
from typing import Sequence

import numpy as np

from nutcracker.codex.smap import decode_smap
from nutcracker.earwax.older_room import read_uint16le
from nutcracker.earwax.older_sizeonly import open_game_resource
from nutcracker.graphics.image import convert_to_pil_image
from nutcracker.sputm.room.pproom import EGA
from nutcracker.utils.funcutils import flatten


def read_uint16les(stream):
    return read_uint16le(stream.read(2))

def parse_strip_ega(height, strip_width, data):
    color = 0
    run = 0
    x = 0
    y = 0

    output = [0 for _ in range(height * strip_width)]
    with io.BytesIO(data) as s:
        while x < 8:
            color = ord(s.read(1))
            if color & 0x80:
                run = color & 0x3F
                if color & 0x40:
                    color = ord(s.read(1))
                    if run == 0:
                        run = ord(s.read(1))
                    for z in range(run):
                        output[y * strip_width + x] = (color & 0xf) if z & 1 else (color >> 4)
                        y += 1
                        if y >= height:
                            y = 0
                            x += 1
                else:
                    if run == 0:
                        run = ord(s.read(1))
                    for z in range(run):
                        output[y * strip_width + x] = output[y * strip_width + x - 1]
                        y += 1
                        if y >= height:
                            y = 0
                            x += 1
            else:
                run = color >> 4
                if run == 0:
                    run = ord(s.read(1))
                for z in range(run):
                    output[y * strip_width + x] = color & 0xf
                    y += 1
                    if y >= height:
                        y = 0
                        x += 1
        return np.asarray(output, dtype=np.uint8).reshape(height, strip_width)


def decode_smap(height: int, width: int, data: bytes) -> Sequence[Sequence[int]]:
    strip_width = 8

    if width == 0 or height == 0:
        return None

    num_strips = width // strip_width
    data = data[2:]

    with io.BytesIO(data) as s:
        offs = [(read_uint16les(s) - 2) for _ in range(num_strips)]
    index = list(zip(offs, offs[1:] + [len(data)]))

    strips = (data[offset:end] for offset, end in index)
    return np.hstack([parse_strip_ega(height, strip_width, data) for data in strips])

EGA_PALETTE = list(EGA.ravel()) + [59 for _ in range(0x300 - 0x30)]


if __name__ == '__main__':
    import argparse
    from .preset import earwax

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--chiper-key', default='0xFF', type=str, help='xor key')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    for filename in files:
        rnam = {}
        root = open_game_resource(filename, chiper_key=int(args.chiper_key, 16))

        basename = pathlib.Path(os.path.basename(os.path.dirname(filename)))
        os.makedirs(basename / 'backgrounds', exist_ok=True)
        os.makedirs(basename / 'objects', exist_ok=True)

        for idx, room in enumerate(root):
            ro = room.children[0]
            assert ro.tag == 'RO', ro.tag
            hd = earwax.find('HD', ro)
            width = read_uint16le(hd.data, 0)
            height = read_uint16le(hd.data, 2)

            im = earwax.find('IM', ro)
            bgim = decode_smap(height, width, im.data)
            imx = convert_to_pil_image(bgim)
            imx.putpalette(EGA_PALETTE)
            imx.save(basename / 'backgrounds' / f'room_{idx:02d}.png')

            for oi in earwax.findall('OI', ro):
                for oc in earwax.findall('OC', ro):
                    obj_id = oi.attribs['gid']
                    if oc.attribs['gid'] == obj_id:
                        assert read_uint16le(oc.data, 4) == obj_id, (read_uint16le(oc.data, 4), obj_id)
                        width = oc.data[9] * 8
                        height = oc.data[15] & 0xF8
                        oiim = decode_smap(height, width, oi.data)
                        imx = convert_to_pil_image(oiim)
                        imx.putpalette(EGA_PALETTE)
                        imx.save(basename / 'objects' / f'object_{obj_id:02d}.png')
