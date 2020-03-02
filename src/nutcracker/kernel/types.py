from dataclasses import dataclass, field, replace

from typing import NamedTuple, Iterable, Sequence

class Chunk(NamedTuple):
    """Chunk made of 4CC header and data
    
    tag: 4CC header

    data: chunk data
    """
    tag: str
    data: bytes

@dataclass
class Element:
    """Indexing metadata for chunk containers
    
    tag: 4CC header

    data: chunk data

    attribs: helper attributes

    children: Contained elements
    """
    tag: str
    data: bytes = field(repr=False)
    attribs: dict
    children: Sequence['Element']

    def content(self, children: Iterable['Element']) -> 'Element':
        return replace(self, children=list(children))

    def chunk(self) -> Chunk:
        """Convert element to chunk"""
        return Chunk(self.tag, self.data)
