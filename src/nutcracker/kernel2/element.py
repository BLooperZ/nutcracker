import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
)

from nutcracker.kernel2.chunk import (
    ArrayBuffer,
    Chunk,
    ChunkSettings,
    mktag,
    read_chunks,
    write_chunks,
)


class Element:
    __slots__ = ('cfg', 'chunk', 'attribs', 'parent', '_children', '_data')

    _children: list['Element'] | None
    _data: bytes | None

    def __init__(
        self,
        cfg: 'IndexerSettings',
        chunk: Chunk,
        attribs: dict[str, Any] | None = None,
        parent: 'Element | None' = None,
    ) -> None:
        self.cfg = cfg
        self.chunk = chunk
        self.attribs = attribs or {}
        self.parent = parent
        self._children = None
        self._data = None

    def update_children(self, children: Iterable['Element']) -> None:
        children = list(children)
        # children should have been mapped already to avoid index offset issues
        assert self._children is not None
        self._children = children
        self.update_raw(
            write_chunks(
                self.cfg,
                (mktag(self.cfg, child.tag, child.data) for child in self.children()),
            )
        )

    def update_raw(self, value: bytes) -> None:
        self._data = value

    def children(self) -> Iterator['Element']:
        schema = self.cfg.schema.get(self.tag)
        if self._children is None:
            if not schema:
                return
            self._children = list(map_chunks(self.cfg, self.data, parent=self))
        yield from self._children

    def add_child(self, child: 'Element') -> None:
        if self._children is None:
            self._children = list(self.children())
        self._children.append(child)

    @property
    def tag(self) -> str:
        return self.chunk.tag

    @property
    def data(self) -> ArrayBuffer:
        if self._data is None:
            return self.chunk.data
        return memoryview(self._data)

    def __repr__(self) -> str:
        attribs = ' '.join(f'{key}={val}' for key, val in self.attribs.items())
        children = ','.join(_format_children(self.children(), max_show=4))
        return f'Element<{self.tag}>[{attribs}, children={{{children}}}]'


def _format_children(
    root: Iterable[Element],
    max_show: int | None = None,
) -> Iterator[str]:
    counts = Counter(str(child.tag) for child in root)
    for idx, (tag, count) in enumerate(counts.items()):
        if not (max_show is None or idx < max_show):
            yield '...'
            return
        yield f'{tag}*{count}' if count > 1 else tag


class MissingSchemaKeyError(Exception):
    def __init__(self, tag: str) -> None:
        super().__init__(f'Missing key in schema: {tag}')
        self.tag = tag


class MissingSchemaEntryError(Exception):
    def __init__(self, tag: str, child_tag: str) -> None:
        super().__init__(f'Missing entry for {child_tag} in {tag} schema')
        self.tag = tag
        self.child_tag = child_tag


@contextmanager
def schema_check(cfg: 'IndexerSettings') -> Iterator[None]:
    try:
        yield
    except (MissingSchemaKeyError, MissingSchemaEntryError) as exc:
        if cfg.errors == 'strict':
            raise
        getattr(cfg, 'logger', logging).warning(exc)


def map_chunks(
    cfg: 'IndexerSettings',
    buffer: ArrayBuffer,
    *,
    parent: Element | None = None,
    offset: int = 0,
) -> Iterator[Element]:
    for coffset, chunk in read_chunks(cfg, buffer, offset):
        elem = Element(
            cfg,
            chunk,
            {
                'offset': coffset,
                'size': len(chunk.data),
                **(cfg.extra(parent, chunk, coffset) if cfg.extra else {}),
            },
        )
        with schema_check(cfg):
            if elem.tag not in cfg.schema:
                raise MissingSchemaKeyError(elem.tag)
            if parent and elem.tag not in cfg.schema[parent.tag]:
                raise MissingSchemaEntryError(parent.tag, elem.tag)
        yield elem


ExtraFunc = Callable[[Element | None, Chunk, int], dict[str, Any]]


@dataclass(frozen=True)
class IndexerSettings(ChunkSettings):
    schema: dict[str, set[str]] = field(default_factory=dict)
    errors: str = 'strict'
    extra: ExtraFunc | None = None


def generate_schema(
    cfg: ChunkSettings,
    buffer: ArrayBuffer,
    parent_tag: str | None = None,
    schema: dict[str, set[str]] | None = None,
) -> dict[str, set[str]]:
    if schema is None:
        schema = defaultdict(set)

    for _, chunk in read_chunks(cfg, buffer):
        tag = chunk.tag

        if parent_tag is not None:
            schema[parent_tag].add(tag)

        if tag in schema and not schema[tag]:
            continue

        try:
            generate_schema(cfg, chunk.data, tag, schema)
        except Exception:
            schema[tag] = set()

    return dict(schema)
