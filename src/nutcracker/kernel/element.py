from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, Iterator, Sequence, Union

from .chunk import Chunk


@dataclass
class Element:
    """Indexing metadata for chunk containers

    chunk: Chunk

    attribs: helper attributes

    children: Contained elements
    """

    chunk: Chunk
    attribs: Dict[str, Any]
    children: Sequence['Element']

    @property
    def tag(self) -> str:
        return self.chunk.tag

    @property
    def data(self) -> bytes:
        return self.chunk.data

    def __iter__(self) -> Iterator['Element']:
        return iter(self.children)

    def content(self, children: Iterable['Element']) -> 'Element':
        return replace(self, children=list(children))

    def __repr__(self) -> str:
        attribs = ' '.join(f'{key}={val}' for key, val in self.attribs.items())
        inner = Counter(child.tag for child in self.children)
        children = ','.join(f'{tag}*{count}' if count > 1 else tag for tag, count in inner.items())
        has_more = ',...' if len(inner) > 3 else ''
        return f'Element<{self.tag}>[{attribs}, children={{{children}{has_more}}}]'


ElementTree = Union[Iterator[Element], Element, None]
