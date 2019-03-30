#!/usr/bin/env python3

from smush import SmushFile, read_chunks
from fobj import unobj, mkobj
from ahdr import parse_header
from codex import get_decoder
from image import save_single_frame_image


import struct

def convert_fobj(datam):
    meta, data = unobj(datam)
    width = meta['x2'] - meta['x1']
    height = meta['y2'] - meta['y1']
    decode = get_decoder(meta['codec'])
    if decode == NotImplemented:
        return None

    if meta['x1'] != 0 or meta['y1'] != 0:
        print('TELL ME')

    locs = {'x1': meta['x1'], 'y1': meta['y1'], 'x2': meta['x2'], 'y2': meta['y2']}
    return locs, decode(width, height, data)

def non_parser(chunk):
    return chunk

def parse_frame(frame, parsers):
    chunks = list(read_chunks(frame))
    return [(tag, parsers.get(tag, non_parser)(chunk)) for tag, chunk in chunks]

def verify_nframes(frames, nframes):
    for idx, frame in enumerate(frames):
        if nframes and idx > nframes:
            raise ValueError('too many frames')
        yield frame

def filter_chunk_once(chunks, target):
    return next((frame for tag, frame in chunks if tag == target), None)

def delta_color(org_color, delta_color):
    t = (org_color * 129 + delta_color) // 128
    t = max(0, t)
    t = min(255, t)
    return t

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with SmushFile(args.filename) as smush_file:
        header = parse_header(smush_file.header)
        print(header['palette'][39])

        palette = header['palette']

        frames = verify_nframes(smush_file, header['nframes'])
        frames = (list(read_chunks(frame)) for frame in frames)

        # parsers = {
        #     'FOBJ': convert_fobj
        # }

        # frames = (frame for idx, frame in enumerate(frames) if 1050 > idx)
        # parsed_frames = list(parse_frame(frame, parsers) for frame in frames)

        # for idx, frame in enumerate(parsed_frames):
        #     print((idx, [tag for tag, chunk in frame]))

        # image_frames = ((filter_chunk_once(parsed, 'FOBJ'), filter_chunk_once(parsed, 'NPAL')) for parsed in parsed_frames)
        # image_frames, pal_frames = zip(*image_frames)
        # frames_pil = save_frame_image(image_frames)

        palette = [x for l in palette for x in l]
        screen = []

        delta_pal = []


        for idx, frame in enumerate(frames):
            print(f'{idx} - {[tag for tag, _ in frame]}')

            for tag, chunk in frame:
                if tag == 'NPAL':
                    palette = list(zip(*[iter(chunk)]*3))
                    palette = [x for l in palette for x in l]
                    continue
                if tag == 'XPAL':

                    sub_size = len(chunk)
                    print(f'{idx} - XPAL {sub_size}')

                    if sub_size == 0x300 * 3 + 4:
                        delta_pal = struct.unpack(f'<{0x300}h', chunk[4:4 + 2 * 0x300])
                        palette = list(zip(*[iter(chunk[4 + 2 * 0x300:])]*3))
                        palette = [x for l in palette for x in l]

                    if sub_size == 6:

                        print(f'{idx} - XPAL 6 {chunk}')
                        palette = [delta_color(palette[i], delta_pal[i]) for i in range(0x300)]
                        print(f'NEW PALETTE: {palette}')

                elif tag == 'FOBJ':
                    screen = convert_fobj(chunk)
                    continue
                else:
                    continue
            im = save_single_frame_image(screen)
            im.putpalette(palette)
            im.save(f'out/FRME_{idx:05d}.png')           
