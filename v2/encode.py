#!/usr/bin/env python3

from image_reader import read_image_grid, resize_frame
from fobj import mkobj
from codex import get_encoder
from smush_writer import mktag

if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--codec', '-c', action='store', type=int, required=True, help='codec for encoding', choices=[21, 44])
    parser.add_argument('--fake', '-f', action='store', type=int, help='fake codec for FOBJ header', choices=[21, 44])
    args = parser.parse_args()

    if args.fake == None:
        args.fake = args.codec

    frames = read_image_grid(args.filename)
    frames = (resize_frame(frame) for frame in frames)
    frames = [frame for frame in frames if frame != None]

    numFrames = len(frames)
    print(numFrames)

    for loc, frame in frames:
        meta = {'codec': args.fake, **loc, 'unk1': 0, 'unk2': 0}
        # print(meta)

        encode = get_encoder(args.codec)

        width = meta['x2'] - meta['x1']
        height = meta['y2'] - meta['y1']

        encoded_frame = encode(width, height, frame)

        fobj = mkobj(meta, encoded_frame)
        # print(mktag('FOBJ', fobj))
