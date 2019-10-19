#!/usr/bin/env python3
import os
import struct
import zlib

from functools import partial
from itertools import chain

from PIL import Image
import numpy as np

from codex.codex import get_decoder, get_encoder
from image import save_single_frame_image
from smush import smush, anim, ahdr, fobj

from typing import List

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        header, frames = anim.parse(res)
        # print(header['palette'][39])

        basename = os.path.basename(args.filename)

        # palette = header['palette']
        mframes = (list(frame) for frame in frames)

        chars = []

        def get_frame_image(idx):
            im = Image.open(f'out/{basename}/FRME_{idx:05d}.png')
            return list(np.asarray(im))

        def encode_fake(image):
            encode = get_encoder(37)
            loc = {'x1': 0, 'y1': 0, 'x2': len(image[0]), 'y2': len(image)}
            meta = {'codec': 37, **loc, 'unk1': 0, 'unk2': 0}
            return fobj.mkobj(meta, encode(image))

        for idx, frame in enumerate(mframes):
            print(f'{idx} - {[tag for _, (tag, _) in frame]}')
            fdata: List[bytes] = []
            for _, (tag, chunk) in frame:
                if tag == 'ZFOB':
                    image = get_frame_image(idx)
                    encoded = encode_fake(image)
                    decompressed_size = struct.pack('>I', len(encoded))
                    fdata += [smush.mktag('ZFOB', decompressed_size + zlib.compress(encoded, 9))]
                    continue
                if tag == 'FOBJ':
                    image = get_frame_image(idx)
                    fdata += [smush.mktag('FOBJ', encode_fake(image))]
                    continue
                else:
                    fdata += [smush.mktag(tag, chunk)]
                    continue
            chars.append(smush.mktag('FRME', smush.write_chunks(fdata)))
        bheader = smush.mktag('AHDR', ahdr.to_bytes(header))
        nut_file = smush.mktag('ANIM', smush.write_chunks(chain([bheader], chars)))
        with open('NEW-VIDEO.SAN', 'wb') as output_file:
            output_file.write(nut_file)
