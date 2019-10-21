#!/usr/bin/env python3
import os

from itertools import chain

from smush.fobj import mkobj
from codex.codex import get_encoder
from smush import smush, anim, ahdr

# LEGACY
def write_nut_file(header, numChars, chars, filename):
    chars = (smush.mktag('FRME', char) for char in chars)
    header = ahdr.create(header, nframes=numChars)
    nut_file = anim.compose(header, chars)
    with open(filename, 'wb') as font_file:
        font_file.write(nut_file)

if __name__=="__main__":
    import argparse

    from graphics import grid

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--codec', '-c', action='store', type=int, required=True, help='codec for encoding', choices=[21, 44])
    parser.add_argument('--fake', '-f', action='store', type=int, help='fake codec for FOBJ header', choices=[21, 44])
    parser.add_argument('--ref', '-r', action='store', type=str, help='reference SMUSH file')
    parser.add_argument('--target', '-t', help='target file', default='out/NEWFONT.NUT')

    args = parser.parse_args()

    if args.fake == None:
        args.fake = args.codec

    frames = grid.read_image_grid(args.filename)
    frames = (grid.resize_frame(frame) for frame in frames)
    frames = [frame for frame in frames if frame != None]

    numFrames = len(frames)
    print(numFrames)

    teste = []

    for loc, frame in frames:
        meta = {'codec': args.fake, **loc, 'unk1': 0, 'unk2': 0}
        # print(meta)

        encode = get_encoder(args.codec)

        width = meta['x2'] - meta['x1']
        height = meta['y2'] - meta['y1']

        encoded_frame = encode(width, height, frame.tolist())

        fobj = mkobj(meta, encoded_frame)
        # print(mktag('FOBJ', fobj))

        teste.append(smush.mktag('FOBJ', fobj))

    with open(args.ref, 'rb') as res:
        header, _ = anim.parse(res)

    os.makedirs(os.path.dirname(args.target), exist_ok=True)
    write_nut_file(header, len(teste), teste, args.target)
