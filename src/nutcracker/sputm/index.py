#!/usr/bin/env python3

import io
import os

def read_directory(data):
    with io.BytesIO(data) as s:
        num = int.from_bytes(s.read(2), byteorder='little', signed=False)
        rnums = [int.from_bytes(s.read(1), byteorder='little', signed=False) for i in range(num)]
        offs = [int.from_bytes(s.read(4), byteorder='little', signed=False) for i in range(num)]
        for rnum, off in zip(rnums, offs):
            print(rnum, off)

if __name__ == '__main__':
    import argparse
    import pprint

    from . import sputm

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:

        s = sputm.generate_schema(res)
        pprint.pprint(s)

        res.seek(0, io.SEEK_SET)
        root = sputm.map_chunks(res, schema=s)
        for t in root:
            sputm.render(t)

            # for lflf in sputm.findall('LFLF', t):
            #     tree = sputm.findpath('ROOM/OBIM/IM{:02x}', lflf)
            #     sputm.render(tree)

        print('==========')
