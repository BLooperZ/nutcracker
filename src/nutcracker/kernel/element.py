from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, Iterator, Optional, Sequence, Union

from .chunk import Chunk

ElementTree = Union[Iterator['Element'], 'Element', None]


@dataclass
class Element(object):
    """Indexing metadata for chunk containers

    chunk: Chunk

    attribs: helper attributes

    children: Contained elements
    """

    chunk: Chunk
    attribs: Dict[str, Any]
    children: Sequence['Element']

    _data: Optional[bytes] = field(default=None, repr=False, init=False)

    @property
    def tag(self) -> str:
        return self.chunk.tag

    @property
    def data(self) -> bytes:
        if self._data is None:
            return self.chunk.data
        return self._data

    @data.setter
    def data(self, value: bytes) -> None:
        self._data = value

    def __iter__(self) -> Iterator['Element']:
        return iter(self.children)

    def content(self, children: Iterable['Element']) -> 'Element':
        return replace(self, children=list(children))

    def __repr__(self) -> str:
        attribs = ' '.join(f'{key}={val}' for key, val in self.attribs.items())
        children = ','.join(_format_children(self, max_show=4))
        return f'Element<{self.tag}>[{attribs}, children={{{children}}}]'


def _format_children(
    root: Iterable[Element],
    max_show: Optional[int] = None,
) -> Iterator[str]:
    counts = Counter(child.tag for child in root)
    for idx, (tag, count) in enumerate(counts.items()):
        if not (max_show is None or idx < max_show):
            yield '...'
            return
        yield f'{tag}*{count}' if count > 1 else tag
