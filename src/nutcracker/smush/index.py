#!/usr/bin/env python3

import io
import os

if __name__ == '__main__':
    import argparse
    import pprint
    import itertools

    from .preset import smush

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        resource = res.read()

    s = smush.generate_schema(resource)
    pprint.pprint(s)

    it = itertools.count()

    def set_frame_id(parent, chunk, offset):
        if chunk.tag != 'FRME':
            return {}
        return {'id': next(it)}


    root = smush(schema=s).map_chunks(resource, extra=set_frame_id) 
    for t in root:
        smush.render(t)
