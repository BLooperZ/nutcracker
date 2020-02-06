#!/usr/bin/env python3

import io
import logging
import os
import struct
from contextlib import contextmanager
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
        if parse(tag, c.tag, evaluate_result=False):
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

class MissingSchemaKey(Exception):
    def __init__(self, tag):
        super().__init__('Missing key in schema: {tag}'.format(tag=tag))
        self.tag = tag

class MissingSchemaEntry(Exception):
    def __init__(self, ptag, tag):
        super().__init__('Missing entry for {tag} in {ptag} schema'.format(ptag=ptag, tag=tag))
        self.ptag = ptag
        self.tag = tag

@contextmanager
def exception_ptag_context(ptag):
    try:
        yield
    except Exception as e:
        if not hasattr(e, 'ptag'):
            e.ptag = ptag
        raise e

@contextmanager
def schema_check(schema, ptag, tag, strict=False, logger=logging):
    try:
        if ptag and tag not in schema[ptag]:
            raise MissingSchemaEntry(ptag, tag)
        if tag not in schema:
            raise MissingSchemaKey(tag)
    except (MissingSchemaKey, MissingSchemaEntry) as e:
        if strict:
            raise e
        else:
            logger.warning(e)
    finally:
        yield

def create_element(schema, tag, offset, data, **kwargs):
    return Element(
        tag,
        {'offset': offset, 'size': len(data)},
        list(map_chunks(data, schema=schema, ptag=tag, **kwargs)) if schema.get(tag) else [],
        data
    )

def map_chunks(data, schema=None, ptag=None, strict=False, **kwargs):
    schema = schema or {}
    chunks = read_chunks(data, **kwargs)
    with exception_ptag_context(ptag):
        for hoff, (tag, chunk) in chunks:
            with schema_check(schema, ptag, tag, strict=strict):
                yield create_element(schema, tag, hoff, chunk, strict=strict, **kwargs)

def generate_schema(data, **kwargs):
    schema = {}
    DATA = frozenset()
    DUMMY = frozenset({10})
    pos = data.tell()  # TODO: check if partial iterations are possible
    while True:
        data.seek(pos, io.SEEK_SET)
        try:
            for elem in map_chunks(data, strict=True, schema=schema, ptag=None, **kwargs):
                pass
            return {ptag: set(tags) for ptag, tags in schema.items() if tags != DUMMY}
        except MissingSchemaKey as miss:
            schema[miss.tag] = DUMMY  # creates new copy
        except MissingSchemaEntry as miss:
            schema[miss.ptag] -= DUMMY
            schema[miss.ptag] |= {miss.tag}
        except Exception as e:
            if schema.get(e.ptag) == DATA:
                raise ValueError('Cannot create schema for given file with given configuration')
            schema[e.ptag] = DATA

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
