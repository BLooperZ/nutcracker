#!/usr/bin/env python3
import glob
import os
import struct
import zlib

from functools import partial
from itertools import chain

from smush import anim, ahdr
from smush.fobj import unobj, mkobj
from codex.codex import get_decoder
from image import save_single_frame_image, save_image_grid
from utils.funcutils import flatten

from typing import Sequence

def clip(lower, upper, value):
    return lower if value < lower else upper if value > upper else value

clip_byte = partial(clip, 0, 255)

def delta_color(org_color, delta_color):
    return clip_byte((129 * org_color + delta_color) // 128)

def convert_fobj(datam):
    meta, data = unobj(datam)
    width = meta['x2'] - meta['x1'] if meta['codec'] != 1 else meta['x2']
    height = meta['y2'] - meta['y1'] if meta['codec'] != 1 else meta['y2']
    decode = get_decoder(meta['codec'])
    if decode == NotImplemented:
        print(f"Codec not implemented: {meta['codec']}")
        return None

    # assert len(datam) % 2 == 0, (basename, meta['codec'])

    if meta['x1'] != 0 or meta['y1'] != 0:
        print('TELL ME')

    print(meta)

    locs = {'x1': meta['x1'], 'y1': meta['y1'], 'x2': meta['x2'], 'y2': meta['y2']}
    return locs, decode(width, height, data)

def generate_frames(header, frames):
    palette = header.palette
    screen: Sequence[int] = []
    delta_pal: Sequence[int] = []

    for idx, frame in enumerate(frames):
        for cidx, (tag, chunk) in enumerate(frame):
            if tag == 'NPAL':
                palette = tuple(chunk)
                continue
            if tag == 'XPAL':
                sub_size = len(chunk)
                print(f'{idx} - XPAL {sub_size}')

                if sub_size == 0x300 * 3 + 4:
                    delta_pal = struct.unpack(f'<{0x300}h', chunk[4:4 + 2 * 0x300])
                    palette = chunk[4 + 2 * 0x300:]

                if sub_size == 6:
                    assert len(delta_pal) == 0x300
                    assert len(palette) == 0x300
                    print(f'{idx} - XPAL 6 {chunk}')
                    palette = [delta_color(pal, delta) for pal, delta in zip(palette, delta_pal)]
                continue
            if tag == 'ZFOB':
                decompressed_size = struct.unpack('>I', chunk[:4])[0]
                chunk = zlib.decompress(chunk[4:])
                assert len(chunk) == decompressed_size
                screen = convert_fobj(chunk)
                continue
            if tag == 'FOBJ':
                screen = convert_fobj(chunk)
                # im = save_single_frame_image(screen)
                # im.putpalette(palette)
                # im.save(f'out/FRME_{idx:05d}_{cidx:05d}.png')   
                continue
            else:
                # print(f'support for tag {tag} not implemented yet')
                continue
        assert palette
        assert screen
        yield palette, screen

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    parser.add_argument('--target', '-t', help='target directory', default='out')
    parser.add_argument('--nut', action='store_true')
    parser.add_argument('--map', action='store_true')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    print(files)
    for filename in files:
        basename = os.path.basename(filename)
        output_dir = os.path.join(args.target, basename)
        os.makedirs(output_dir, exist_ok=True)
        print(f'Decoding file: {basename}')
        with open(filename, 'rb') as res:
            header, frames = anim.parse(res)
            if args.map:
                list(chain.from_iterable(frames))
                exit(0)
            if not args.nut:
                for idx, (palette, screen) in enumerate(generate_frames(header, frames)):
                    im = save_single_frame_image(screen)
                    # im = im.crop(box=(0,0,320,200))
                    im.putpalette(palette)
                    im.save(os.path.join(output_dir, f'FRME_{idx:05d}.png'))
            else:
                chars = (frame for _, frame in generate_frames(header, frames))
                save_image_grid(
                    os.path.join(output_dir, 'chars.png'),
                    chars,
                    header.palette,
                    transparency=39
                )
