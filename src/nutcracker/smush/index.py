#!/usr/bin/env python3

import io
import os

if __name__ == '__main__':
    import argparse
    import pprint

    from . import smush

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:

        s = smush.generate_schema(res)
        pprint.pprint(s)

        res.seek(0, io.SEEK_SET)
        root = smush.map_chunks(res, schema=s)
        for t in root:
            smush.render(t)

            # for lflf in sputm.findall('LFLF', t):
            #     tree = sputm.findpath('ROOM/OBIM/IM{:02x}', lflf)
            #     sputm.render(tree)

        print('==========')
