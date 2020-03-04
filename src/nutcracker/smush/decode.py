#!/usr/bin/env python3

import io
import os
from nutcracker.kernel.types import Element

def check_tag(target: str, elem: Element):
    if not elem:
        raise ValueError(f'no 4CC header')
    if elem.tag != target:
        raise ValueError(f'expected tag to be {target} but got {elem.tag}')
    return elem

def read_elements(target: str, elem: Element):
    return iter(check_tag(target, elem).children)

def read_data(target: str, elem: Element):
    return check_tag(target, elem).data

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

    anim = read_elements('ANIM', next(smush(schema=s).map_chunks(resource)))
    ahdr = read_data('AHDR', next(anim))
    for elem in anim:
        smush.render(elem)
