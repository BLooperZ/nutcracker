from dataclasses import dataclass, field, replace

from typing import NamedTuple, Iterator, Sequence

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

    def content(self, children: Iterator['Element']) -> 'Element':
        return replace(self, children=list(children))
