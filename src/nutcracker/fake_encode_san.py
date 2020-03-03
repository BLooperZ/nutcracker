#!/usr/bin/env python3
import os
import struct
import zlib

from functools import partial
from itertools import chain

from PIL import Image
import numpy as np

from nutcracker.codex.codex import get_decoder, get_encoder
from nutcracker.image import save_single_frame_image
from nutcracker.smush import anim, ahdr, fobj
from nutcracker.smush.preset import smush

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

        def encode_fake(image, chunk):
            meta, data = fobj.unobj(chunk)
            codec = meta['codec']
            if codec == 1:
                return chunk
            encode = get_encoder(codec)
            loc = {'x1': 0, 'y1': 0, 'x2': len(image[0]), 'y2': len(image)}
            meta = {'codec': codec, **loc, 'unk1': 0, 'unk2': 0}
            print('CODEC', meta)
            encoded = encode(image)
            return fobj.mkobj(meta, encoded)

        for idx, frame in enumerate(mframes):
            print(f'{idx} - {[tag for _, (tag, _) in frame]}')
            fdata: List[bytes] = []
            for _, (tag, chunk) in frame:
                if tag == 'ZFOB':
                    image = get_frame_image(idx)
                    decompressed_size = struct.unpack('>I', chunk[:4])[0]
                    chunk = zlib.decompress(chunk[4:])
                    assert len(chunk) == decompressed_size
                    encoded = encode_fake(image, chunk)
                    decompressed_size = struct.pack('>I', len(encoded))
                    fdata += [smush.mktag('ZFOB', decompressed_size + zlib.compress(encoded, 9))]
                    continue
                if tag == 'FOBJ':
                    image = get_frame_image(idx)
                    fdata += [smush.mktag('FOBJ', encode_fake(image, chunk))]
                    continue
                else:
                    fdata += [smush.mktag(tag, chunk)]
                    continue
            chars.append(smush.mktag('FRME', smush.write_chunks(fdata)))
        bheader = smush.mktag('AHDR', ahdr.to_bytes(header))
        nut_file = smush.mktag('ANIM', smush.write_chunks(chain([bheader], chars)))
        with open('NEW-VIDEO.SAN', 'wb') as output_file:
            output_file.write(nut_file)
