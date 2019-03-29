#!/usr/bin/env python3

from smush import SmushFile, read_chunks
from fobj import unobj, mkobj
from ahdr import parse_header
from codex import get_decoder
from image import save_image_grid, save_frame_image

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

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with SmushFile(args.filename) as smush_file:
        header = parse_header(smush_file.header)
        print(header['palette'][39])

        frames = verify_nframes(smush_file, header['nframes'])

        parsers = {
            'FOBJ': convert_fobj
        }

        # frames = (frame for idx, frame in enumerate(frames) if idx < 10)
        parsed_frames = (parse_frame(frame, parsers) for frame in frames)

        # for idx, frame in enumerate(parsed_frames):
        #     print((idx, [tag for tag, chunk in frame]))

        image_frames = (filter_chunk_once(parsed, 'FOBJ') for parsed in parsed_frames)
        image_frames = (frame for frame in image_frames if frame != None)

        save_as_grid = False
        if save_as_grid:
            save_image_grid('chars.png', image_frames, header['palette'], transparency=39)
        else:
            frames_pil = save_frame_image(image_frames, header['palette'], transparency=39)
            for idx, im in enumerate(frames_pil):
                im.save(f'out/FRME_{idx:05d}.png')
