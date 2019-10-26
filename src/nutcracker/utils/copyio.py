import io
import functools
from typing import Callable, Optional

def buffered(source: Callable[[Optional[int]], bytes], buffer_size : int = io.DEFAULT_BUFFER_SIZE):
    return iter(functools.partial(source, buffer_size), b'')
