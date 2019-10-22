#!/usr/bin/env python3
import io
import os
import struct

from functools import partial

if __name__ == '__main__':
    import argparse

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        lecf = sputm.assert_tag('LECF', sputm.untag(res))
        assert res.read() == b''
        # chunks = (assert_tag('LFLF', chunk) for chunk in read_chunks(tlkb))
        chunks = sputm.print_chunks(sputm.read_chunks(lecf))
        for idx, (hoff, (tag, chunk)) in enumerate(chunks):
            if not tag == 'LFLF':
                continue
            if idx == 87:  # uncomment to skip failing tag after AKOS in FT.LA1
                with open('CHUNK_0087.DAT', 'wb') as f:
                    f.write(chunk)
                continue
            print([tag for _, (tag, _) in sputm.read_chunks(chunk)])
            for cidx, (off, (tag, data)) in enumerate(sputm.read_chunks(chunk)):
                if tag == 'SCRP':
                    os.makedirs('SCRIPTS', exist_ok=True)
                    with open(os.path.join('SCRIPTS', f'SCRP_{cidx:04d}_{idx:04d}'), 'wb') as out:
                        out.write(sputm.mktag('SCRP', data))
                    continue
                if tag == 'DIGI':
                    os.makedirs('DIGIS', exist_ok=True)
                    with open(os.path.join('DIGIS', f'DIGI_{cidx:04d}_{idx:04d}'), 'wb') as out:
                        out.write(sputm.mktag('DIGI', data))
                if tag == 'TLKE':
                    print(data)
                    exit(1)
                if tag == 'CHAR':
                    os.makedirs('CHARS', exist_ok=True)
                    with open(os.path.join('CHARS', f'CHAR_{cidx:04d}_{idx:04d}'), 'wb') as out:
                        out.write(sputm.mktag('CHAR', data))
                if tag == 'RMDA':
                    os.makedirs('ROOMS', exist_ok=True)
                    with open(os.path.join('ROOMS', f'ROOM_{cidx:04d}_{idx:04d}'), 'wb') as out:
                        out.write(sputm.mktag('ROOM', data))

                if tag == 'SOUN':
                    os.makedirs('SOUNDS', exist_ok=True)
                    with open(os.path.join('SOUNDS', f'{hoff + off + 16:08x}.voc'), 'wb') as out:
                        out.write(data)
            # save raw
            print('==========')
