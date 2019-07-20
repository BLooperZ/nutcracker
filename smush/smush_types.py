from typing import NamedTuple, Optional, Tuple, Sequence

# Chunk = Tuple[str, bytes]
class Chunk(NamedTuple):
    tag: str
    data: bytes

class AnimationHeader(NamedTuple):
    version: int
    nframes: int
    unk1: int
    palette: Sequence[int]
    secondary_version: Optional[int]
    unk2: Optional[int]
    sound_freq: Optional[int]
    zero1: Optional[int]
    zero2: Optional[int]
