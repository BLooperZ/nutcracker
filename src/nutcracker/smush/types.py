from typing import NamedTuple, Optional, Tuple, Sequence

from nutcracker.core.types import Chunk

class AnimationHeader(NamedTuple):
    version: int
    nframes: int
    dummy: int
    palette: Sequence[int]
    framerate: Optional[int]
    maxframe: Optional[int]
    samplerate: Optional[int]
    dummy2: Optional[int]
    dummy3: Optional[int]
