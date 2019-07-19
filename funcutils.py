
from typing import Iterable, Iterator, Sequence, TypeVar

T = TypeVar('T')

def flatten(ls: Iterable[Iterable[T]]) -> Iterator[T]: 
    return (item for sublist in ls for item in sublist)

def grouper(it, chunk_size):
    return zip(*([iter(it)] * chunk_size))
