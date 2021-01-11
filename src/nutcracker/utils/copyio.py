import io
import functools
from typing import Callable, Optional, Iterator


def buffered(
    source: Callable[[Optional[int]], bytes], buffer_size: int = io.DEFAULT_BUFFER_SIZE
) -> Iterator[bytes]:
    return iter(functools.partial(source, buffer_size), b'')
