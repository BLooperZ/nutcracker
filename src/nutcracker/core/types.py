from typing import NamedTuple

from .stream import StreamView

# Chunk = Tuple[str, bytes]
class Chunk(NamedTuple):
    tag: str
    data: StreamView
