from typing import NamedTuple

# Chunk = Tuple[str, bytes]
class Chunk(NamedTuple):
    tag: str
    data: bytes
