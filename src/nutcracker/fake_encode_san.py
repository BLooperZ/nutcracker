#!/usr/bin/env python3
from dataclasses import asdict
import os
from itertools import chain

from PIL import Image
import numpy as np

from nutcracker.codex.codex import get_encoder
from nutcracker.graphics.image import ImagePosition
from nutcracker.kernel.types import Element
from nutcracker.smush import anim, ahdr, fobj
from nutcracker.smush.preset import smush

from typing import List, Sequence


def encode_san(root: Element) -> bytes:
    header, frames = anim.parse(root)
    # split frames to sequences
    # for frames in each sequence (range?)
    # if any of the frame images in the sequence exists in parameter
    # re-encode sequence
    # yield each frame
    return b''


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    root = anim.from_path(args.filename)
    header, frames = anim.parse(root)
    # print(header['palette'][39])

    basename = os.path.basename(args.filename)

    # palette = header['palette']
    mframes = (list(frame) for frame in frames)

    chars = []

    def get_frame_image(idx: int) -> Sequence[Sequence[int]]:
        im = Image.open(f'out/{basename}/FRME_{idx:05d}.png')
        return list(np.asarray(im))

    def encode_fake(image: Sequence[Sequence[int]], chunk: bytes) -> bytes:
        meta = fobj.unobj(chunk).header
        codec = meta.codec
        if codec == 1:
            return chunk
        encode = get_encoder(codec)
        loc = ImagePosition(x1=0, y1=0, x2=len(image[0]), y2=len(image))
        meta = fobj.FrameObjectHeader(codec=codec, **asdict(loc))
        print('CODEC', meta)
        encoded = encode(image)
        return fobj.mkobj(meta, encoded)

    for idx, frame in enumerate(mframes):
        print(f'{idx} - {[elem.tag for elem in frame]}')
        fdata: List[bytes] = []
        for comp in frame:
            if comp.tag == 'ZFOB':
                image = get_frame_image(idx)
                encoded = encode_fake(image, fobj.decompress(comp.data))
                fdata += [smush.mktag('ZFOB', fobj.compress(encoded))]
                continue
            if comp.tag == 'FOBJ':
                image = get_frame_image(idx)
                fdata += [smush.mktag('FOBJ', encode_fake(image, comp.data))]
                continue
            else:
                fdata += [smush.mktag(comp.tag, comp.data)]
                continue
        chars.append(smush.mktag('FRME', smush.write_chunks(fdata)))
    bheader = smush.mktag('AHDR', ahdr.to_bytes(header))
    nut_file = smush.mktag('ANIM', smush.write_chunks(chain([bheader], chars)))
    with open('NEW-VIDEO.SAN', 'wb') as output_file:
        output_file.write(nut_file)
