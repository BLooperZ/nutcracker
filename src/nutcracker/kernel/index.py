#!/usr/bin/env python3

from contextlib import contextmanager
from dataclasses import replace
from typing import Any, Callable, Dict, FrozenSet, Iterator, Optional, Set

from .resource import read_chunks
from .settings import _IndexSetting
from .chunk import Chunk, IFFChunk
from .element import Element


class MissingSchemaKey(Exception):
    def __init__(self, tag: str) -> None:
        super().__init__(f'Missing key in schema: {tag}')
        self.tag = tag


class MissingSchemaEntry(Exception):
    def __init__(self, ptag: str, tag: str) -> None:
        super().__init__(f'Missing entry for {tag} in {ptag} schema')
        self.ptag = ptag
        self.tag = tag


@contextmanager
def exception_ptag_context(ptag: Optional[str]) -> Iterator[None]:
    try:
        yield
    except Exception as e:
        if not hasattr(e, 'ptag'):
            e.ptag = ptag  # type: ignore
        raise e


def check_schema(cfg: _IndexSetting, ptag: Optional[str], tag: str) -> None:
    try:
        if ptag and tag not in cfg.schema[ptag]:
            raise MissingSchemaEntry(ptag, tag)
        if tag not in cfg.schema:
            raise MissingSchemaKey(tag)
    except (MissingSchemaKey, MissingSchemaEntry) as e:
        if cfg.strict:
            raise e
        else:
            cfg.logger.warning(e)


def create_element(offset: int, chunk: Chunk, **attrs: Any) -> Element:
    return Element(chunk, {'offset': offset, 'size': len(chunk.data), **attrs}, [])


def map_chunks(
    cfg: _IndexSetting,
    data: bytes,
    parent: Optional[Element] = None,
    level: int = 0,
    extra: Optional[Callable[[Optional[Element], Chunk, int], Dict[str, Any]]] = None,
) -> Iterator[Element]:
    ptag = parent.tag if parent else None
    if cfg.max_depth and level >= cfg.max_depth:
        return
    if parent and not cfg.schema.get(parent.tag):
        return
    data = memoryview(data)
    with exception_ptag_context(ptag):
        for offset, chunk in read_chunks(cfg, data):
            check_schema(cfg, ptag, chunk.tag)

            elem = create_element(
                offset, chunk, **(extra(parent, chunk, offset) if extra else {})
            )
            yield elem.content(
                map_chunks(cfg, chunk._buffer[chunk._slice], parent=elem, level=level + 1, extra=extra)
            )


def generate_schema(cfg: _IndexSetting, data: bytes) -> Dict[str, Set[str]]:
    EMPTY: FrozenSet[str] = frozenset()
    DUMMY: FrozenSet[str] = frozenset({'__DUMMY__'})

    schema: Dict[str, FrozenSet[str]] = {}

    # TODO: check if partial iterations are possible
    while True:
        cfg = replace(cfg, schema=schema, strict=True)
        try:
            # generate schema for 1 level deeper
            for _ in map_chunks(cfg, data, level=-1):
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
                raise ValueError(
                    'Cannot create schema for given file with given configuration'
                )
            schema[e.ptag] = EMPTY  # type: ignore


if __name__ == '__main__':
    import argparse
    import os
    from pprint import pprint

    import yaml

    from nutcracker.utils.fileio import read_file

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

    cfg = _IndexSetting(
        chunk=IFFChunk(size_fix=args.size_fix),
        align=args.align,
        max_depth=args.max_depth,
    )

    schema = None
    if args.schema:
        with open(args.schema, 'r') as f:
            schema = yaml.safe_load(f)

    data = read_file(args.filename, key=int(args.chiper_key, 16))

    schema = schema or generate_schema(cfg, data)

    pprint(schema)

    if args.schema_dump:
        with open(args.schema_dump, 'w') as f:
            yaml.dump(schema, f)

    def update_element_path(
        parent: Optional[Element], chunk: Chunk, offset: int
    ) -> Dict[str, str]:
        dirname = parent.attribs['path'] if parent else ''
        res = {'path': os.path.join(dirname, chunk.tag)}
        return res

    root = map_chunks(replace(cfg, schema=schema), data, extra=update_element_path)
    for t in root:
        tree.render(t)
