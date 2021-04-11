#!/usr/bin/env python3
import os
from dataclasses import asdict, replace
from typing import Iterable, Iterator, Tuple

from nutcracker.codex.codex import get_encoder
from nutcracker.graphics.image import ImagePosition, TImage
from nutcracker.smush import anim
from nutcracker.smush.ahdr import AnimationHeader
from nutcracker.smush.fobj import FrameObjectHeader, mkobj
from nutcracker.smush.preset import smush
from nutcracker.utils.fileio import write_file


# LEGACY
def make_nut_file(
    header: AnimationHeader,
    num_chars: int,
    chars: Iterable[bytes],
) -> bytes:
    chars = (smush.mktag('FRME', char) for char in chars)
    header = replace(header, nframes=num_chars)
    return anim.compose(header, chars)


def encode_frame_objects(
    frames: Iterable[Tuple[ImagePosition, TImage]],
    codec: int,
    fake: int,
) -> Iterator[bytes]:
    for loc, frame in frames:
        meta = FrameObjectHeader(codec=fake, **asdict(loc))
        print(meta)

        encode = get_encoder(codec)

        width = meta.x2 - meta.x1
        height = meta.y2 - meta.y1

        encoded_frame = encode(width, height, frame.tolist())

        fobj = mkobj(meta, encoded_frame)
        # print(mktag('FOBJ', fobj))

        yield smush.mktag('FOBJ', fobj)


if __name__ == '__main__':
    import argparse

    from nutcracker.graphics import grid

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument(
        '--codec',
        '-c',
        action='store',
        type=int,
        required=True,
        help='codec for encoding',
        choices=[21, 44],
    )
    parser.add_argument(
        '--fake',
        '-f',
        action='store',
        type=int,
        help='fake codec for FOBJ header',
        choices=[21, 44],
    )
    parser.add_argument(
        '--ref',
        '-r',
        action='store',
        type=str,
        help='reference SMUSH file',
    )
    parser.add_argument('--target', '-t', help='target file', default='out/NEWFONT.NUT')

    args = parser.parse_args()

    if args.fake is None:
        args.fake = args.codec

    frames = grid.read_image_grid(args.filename)
    frames = (grid.resize_frame(frame) for frame in frames)
    frames = [frame for frame in frames if frame is not None]

    num_frames = len(frames)
    print(num_frames)

    fobjs = list(encode_frame_objects(frames, args.codec, args.fake))

    root = anim.from_path(args.ref)
    header, _ = anim.parse(root)

    os.makedirs(os.path.dirname(args.target), exist_ok=True)
    write_file(args.target, make_nut_file(header, len(fobjs), fobjs))
