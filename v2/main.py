#!/usr/bin/env python3

from smush import SmushFile, read_chunks
from fobj import unobj, mkobj
from ahdr import parse_header
from codex import get_decoder
from image import save_image, save_image_grid

def cor_manager(cors):
    def parse_chunks(frame_idx, chunks):
        return (cors[t](frame_idx, chunk) for t, chunk in chunks if t in cors_map)

    return parse_chunks

def convert_fobj(idx, datam):
    meta, data = unobj(datam)
    # if meta['codec'] in (1, 3):
    #     print((idx, 'FOUND'))
    width = meta['x2'] - meta['x1']
    height = meta['y2'] - meta['y1']
    decode = get_decoder(meta['codec'])
    if decode == NotImplemented:
        return None

    if meta['x1'] != 0 or meta['y1'] != 0:
        print('TELL ME')

    locs = {'x1': meta['x1'], 'y1': meta['y1'], 'x2': meta['x2'], 'y2': meta['y2']}
    return locs, decode(width, height, data)

def image_cor(frames, palette):
    max_height = 0
    max_width = 0

    for loc, char in frames:
        if loc['x2'] > max_width:
            max_width = (int(loc['x2'] / 12) + 1) * 12
        if loc['y2'] > max_height:
            max_height = (int(loc['y2'] / 12) + 1) * 12

    save_image('chars.png', frames, palette, max_height, max_width, transparency=39)

def image_cor2(frames, palette):
    save_image_grid('chars.png', frames, palette, transparency=39)

if __name__=='__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    cors_map = {
        'FOBJ': convert_fobj
    }

    parse_chunks = cor_manager(cors_map)

    with SmushFile(args.filename) as smush_file:
        # header, *frames = read_smush_file(args.filename)
        header = parse_header(smush_file.header)
        print(header['palette'][39])

        fframes = []

        for idx, frame in enumerate(smush_file):
            if idx > header['nframes']:
                raise ValueError('too many frames')
            chunks = list(read_chunks(frame))

            # print((idx, [t for t, c in chunks]))

            parsed = parse_chunks(idx, chunks)

            rel = [frame for frame in parsed if frame != None]
            fframes += [(loc, frame) for loc, frame in rel if frame != None]

        image_cor2(fframes, header['palette'])
