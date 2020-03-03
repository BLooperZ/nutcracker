#!/usr/bin/env python3

import io
import os

if __name__ == '__main__':
    import argparse
    import pprint

    from .preset import smush

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        resource = res.read()

    s = smush.generate_schema(resource)
    pprint.pprint(s)

    anim = next(smush(schema=s).map_chunks(resource))
    ahdr = smush.find(anim, 'AHDR')
    for elem in smush.findall(anim, 'FRME'):
        smush.render(elem)
        exit(1)


