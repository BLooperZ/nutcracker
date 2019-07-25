from typing import NamedTuple, Optional, Tuple, Sequence

from res.res_types import Chunk

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
