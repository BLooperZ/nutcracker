from typing import Iterable, Iterator, Tuple

from .chunk import Chunk


def assert_tag(target: str, chunk: Chunk) -> bytes:
    """Return chunk data if chunk has target 4CC tag."""
    if chunk.tag != target:
        raise ValueError(f'expected tag to be {target} but got {chunk.tag}')
    return chunk.data


def print_chunks(
    chunks: Iterable[Tuple[int, Chunk]], level: int = 0, base: int = 0
) -> Iterator[Tuple[int, Chunk]]:
    indent = '    ' * level
    for offset, chunk in chunks:
        print(f'{indent}{base + offset} {chunk.tag} {len(chunk.data)}')
        yield base + offset, chunk


def drop_offsets(chunks: Iterable[Tuple[int, Chunk]]) -> Iterator[Chunk]:
    """Drop offset from each (offset, chunk) tuple in given iterator"""
    return (chunk for _, chunk in chunks)
