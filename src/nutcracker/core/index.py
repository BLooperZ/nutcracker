#!/usr/bin/env python3

import io
import logging
import os
import struct
from typing import Sequence, NamedTuple, Optional, Iterator
from dataclasses import dataclass

from parse import parse

from .resource import read_chunks
from .stream import StreamView

@dataclass
class Element:
    tag: str
    attribs: dict
    children: Sequence['Element']
    data: StreamView

def findall(tag: str, root: Optional[Element]) -> Iterator[Element]:
    if not root:
        return
    for c in root.children:
        if parse(tag, c.tag):
            yield c

def find(tag: str, root: Optional[Element]) -> Optional[Element]:
    return next(findall(tag, root), None)

def findpath(path: str, root: Optional[Element]) -> Optional[Element]:
    path = os.path.normpath(path)
    if not path or path == '.':
        return root
    dirname, basename = os.path.split(path)
    return find(basename, findpath(dirname, root))

def render(element, level=0):
    if not element:
        return
    attribs = ''.join(f' {key}="{value}"' for key, value in element.attribs.items())
    indent = '    ' * level
    closing = '' if element.children else ' /'
    print(f'{indent}<{element.tag}{attribs}{closing}>')
    if element.children:
        for c in element.children:
            render(c, level=level + 1)
        print(f'{indent}</{element.tag}>')

def map_chunks(data, schema={}, ptag=None, **kwargs):
    chunks = read_chunks(data, **kwargs)
    for hoff, (tag, chunk) in chunks:
        if ptag and tag not in schema[ptag]:
            logging.warning('Missing entry for {} in {} schema'.format(tag, ptag))
            exit(1)
        if tag not in schema:
            logging.warning('Missing key in schema: {}'.format(tag))
            exit(1)
        yield Element(
            tag,
            {'offset': hoff, 'size': len(chunk)},
            list(map_chunks(chunk, schema=schema, ptag=tag, **kwargs)) if schema.get(tag) else [],
            chunk
        )

def create_maptree(data):
    return next(map_chunks(data), None)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    with open(args.filename, 'rb') as res:
        root = map_chunks(res)
        for t in root:
            render(t)
