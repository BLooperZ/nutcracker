#!/usr/bin/env python3
import zlib
import struct

from functools import partial

import smush

from fobj import unobj, mkobj
import ahdr
from codex import get_decoder
from image import save_single_frame_image

from typing import Sequence

def clip(lower, upper, value):
    return lower if value < lower else upper if value > upper else value

clip_byte = partial(clip, 0, 255)

def convert_fobj(datam):
    meta, data = unobj(datam)
    width = meta['x2'] - meta['x1'] if meta['codec'] != 1 else meta['x2']
    height = meta['y2'] - meta['y1'] if meta['codec'] != 1 else meta['y2']
    decode = get_decoder(meta['codec'])
    if decode == NotImplemented:
        print(f"Codec not implemented: {meta['codec']}")
        return None

    if meta['x1'] != 0 or meta['y1'] != 0:
        print('TELL ME')

    print(meta)

    locs = {'x1': meta['x1'], 'y1': meta['y1'], 'x2': meta['x2'], 'y2': meta['y2']}
    return locs, decode(width, height, data)

def non_parser(chunk):
    return chunk

def parse_frame(frame, parsers):
    chunks = list(smush.read_chunks(frame))
    return [(tag, parsers.get(tag, non_parser)(chunk)) for tag, chunk in chunks]

def verify_nframes(frames, nframes):
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes:
            raise ValueError('too many frames')
        yield frame

def filter_chunk_once(chunks, target):
    return next((frame for tag, frame in chunks if tag == target), None)

def delta_color(org_color, delta_color):
    return clip_byte((org_color * 129 + delta_color) // 128)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with smush.open(args.filename) as smush_file:
        header = ahdr.parse_header(smush_file.header)
        print(header['palette'][39])

        palette = header['palette']

        frames = verify_nframes(smush_file, header['nframes'])
        frames = (list(smush.read_chunks(frame)) for frame in frames)

        palette = [x for l in palette for x in l]

        screen: Sequence[int] = []
        delta_pal: Sequence[int] = []

        for idx, frame in enumerate(frames):
            for cidx, (tag, chunk) in enumerate(frame):
                if tag == 'NPAL':
                    palette = list(ahdr.grouper(chunk, 3))
                    palette = [x for l in palette for x in l]
                    continue
                if tag == 'XPAL':
                    sub_size = len(chunk)
                    print(f'{idx} - XPAL {sub_size}')

                    if sub_size == 0x300 * 3 + 4:
                        delta_pal = struct.unpack(f'<{0x300}h', chunk[4:4 + 2 * 0x300])
                        palette = list(ahdr.grouper(chunk[4 + 2 * 0x300:], 3))
                        palette = [x for l in palette for x in l]

                    if sub_size == 6:
                        assert delta_pal
                        print(f'{idx} - XPAL 6 {chunk}')
                        palette = [delta_color(palette[i], delta_pal[i]) for i in range(0x300)]
                        # print(f'NEW PALETTE: {palette}')
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
                    # print(f'TAG {tag} not implemented yet')
                    continue
            assert palette
            assert screen
            im = save_single_frame_image(screen)
            # im = im.crop(box=(0,0,320,200))
            im.putpalette(palette)
            im.save(f'out/FRME_{idx:05d}.png')        
