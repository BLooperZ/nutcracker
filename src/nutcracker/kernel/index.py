#!/usr/bin/env python3

import io
import logging
from contextlib import contextmanager
from dataclasses import replace
from typing import Dict, Iterator, FrozenSet, Set

from .resource import read_chunks
from .types import Element, Chunk
from .settings import _IndexSetting

class MissingSchemaKey(Exception):
    def __init__(self, tag):
        super().__init__(f'Missing key in schema: {tag}')
        self.tag = tag

class MissingSchemaEntry(Exception):
    def __init__(self, ptag, tag):
        super().__init__(f'Missing entry for {tag} in {ptag} schema')
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

def check_schema(cfg: _IndexSetting, ptag, tag, logger=logging):
    try:
        if ptag and tag not in cfg.schema[ptag]:
            raise MissingSchemaEntry(ptag, tag)
        if tag not in cfg.schema:
            raise MissingSchemaKey(tag)
    except (MissingSchemaKey, MissingSchemaEntry) as e:
        if cfg.strict:
            raise e
        else:
            logger.warning(e)

def create_element(offset: int, chunk: Chunk, children: Iterator[Element], **attrs) -> Element:
    return Element(
        *chunk,
        {'offset': offset, 'size': len(chunk.data), **attrs},
        list(children)
    )

def map_chunks(cfg: _IndexSetting, data: bytes, ptag: str = None, idgen=None, pid=None) -> Iterator[Element]:
    if cfg.max_depth is None or cfg.max_depth > 0:
        if ptag and not cfg.schema.get(ptag):
            return
        idgen = idgen or {}
        subcfg = replace(cfg, max_depth=cfg.max_depth and cfg.max_depth - 1)
        with exception_ptag_context(ptag):
            for offset, chunk in read_chunks(cfg, data):
                check_schema(cfg, ptag, chunk.tag)

                gid = idgen.get(chunk.tag)
                gid = gid and gid(pid, chunk.data, offset)

                elem = create_element(
                    offset,
                    chunk,
                    map_chunks(subcfg, chunk.data, ptag=chunk.tag, pid=gid),
                    gid=gid and f'{gid:04d}'
                )
                yield elem

def generate_schema(cfg: _IndexSetting, data) -> Dict[str, Set[str]]:
    EMPTY: FrozenSet[str] = frozenset()
    DUMMY: FrozenSet[str] = frozenset({'__DUMMY__'})

    schema: Dict[str, FrozenSet[str]] = {}

    # TODO: check if partial iterations are possible
    while True:
        # generate schema for 1 level deeper
        cfg = replace(cfg, schema=schema, strict=True, max_depth=cfg.max_depth and cfg.max_depth + 1)
        try:
            for _ in map_chunks(cfg, data):
                pass
            return {ptag: set(tags) for ptag, tags in schema.items() if tags != DUMMY}
        except MissingSchemaKey as miss:
            schema[miss.tag] = DUMMY  # creates new copy
        except MissingSchemaEntry as miss:
            schema[miss.ptag] -= DUMMY
            schema[miss.ptag] |= {miss.tag}
        except Exception as e:
            # pylint: disable=no-member
            assert hasattr(e, 'ptag')
            if schema.get(e.ptag) == EMPTY:  # type: ignore
                raise ValueError('Cannot create schema for given file with given configuration')
            schema[e.ptag] = EMPTY  # type: ignore


if __name__ == '__main__':
    import argparse
    from pprint import pprint

    import yaml

    from nutcracker.chiper import xor

    from . import tree

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--size-fix', default=0, type=int, help='header size fix')
    parser.add_argument('--align', default=1, type=int, help='alignment between chunks')
    parser.add_argument('--schema', type=str, help='load saved schema from file')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    parser.add_argument('--max-depth', default=None, type=int, help='max depth')
    parser.add_argument('--schema-dump', type=str, help='save schema to file')
    args = parser.parse_args()

    cfg = _IndexSetting(size_fix=args.size_fix, align=args.align, max_depth=args.max_depth)

    schema = None
    if args.schema:
        with open(args.schema, 'r') as f:
            schema = yaml.safe_load(f)

    with open(args.filename, 'rb') as res:
        data = xor.read(res, key=int(args.chiper_key, 16))

    schema = schema or generate_schema(cfg, data)

    pprint(schema)

    if args.schema_dump:
        with open(args.schema_dump, 'w') as fb:
            yaml.dump(schema, f)

    root = map_chunks(replace(cfg, schema=schema), data)
    for t in root:
        tree.render(t)
