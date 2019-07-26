from itertools import chain

from typing import Iterable, Iterator, Sequence, TypeVar

T = TypeVar('T')

def flatten(ls: Iterable[Iterable[T]]) -> Iterator[T]:
    # flatten(['ABC', 'DEF']) --> A B C D E F
    "Flatten one level of nesting."
    return chain.from_iterable(ls)

def grouper(iterable: Iterable[T], n: int, fillvalue: T = None) -> Iterator[Sequence[T]]:
    """Collect data into fixed-length chunks or blocks."""
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)
