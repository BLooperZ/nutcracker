from itertools import chain

from typing import Iterable, Iterator, Sequence, TypeVar

T = TypeVar('T')

def flatten(ls: Iterable[Iterable[T]]) -> Iterator[T]: 
    "Flatten one level of nesting"
    return chain.from_iterable(ls)

def grouper(it, chunk_size):
    return zip(*([iter(it)] * chunk_size))
