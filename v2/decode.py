#!/usr/bin/env python3

from smush import SmushFile, read_chunks
from fobj import unobj, mkobj
from ahdr import parse_header
from codex import get_decoder
from image import save_image, save_image_grid

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

if __name__=='__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with SmushFile(args.filename) as smush_file:
        header = parse_header(smush_file.header)
        print(header['palette'][39])

        for idx, frame in enumerate(smush_file):
            if idx > header['nframes']:
                raise ValueError('too many frames')
            chunks = list(read_chunks(frame))

            # print((idx, [t for t, c in chunks]))

            parsed = convert_fobj(idx, chunks)

            rel = [frame for frame in parsed if frame != None]
            frames = [(loc, frame) for loc, frame in rel if frame != None]

        save_image_grid('chars.png', frames, header['palette'], transparency=39)
