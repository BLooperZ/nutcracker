import io
from typing import Optional

from nutcracker.kernel.buffer import BufferLike, UnexpectedBufferSize


def decode_line(src: BufferLike, decoded_size: Optional[int] = None) -> bytes:
    buffer = bytearray()
    with io.BytesIO(src) as stream:
        while stream.tell() < len(src):

            if decoded_size and len(buffer) >= decoded_size:
                rest = stream.read()
                assert rest in {b'', b'\x00'}, rest
                break

            code = stream.read(1)[0]
            run_len = (code // 2) + 1
            run_line = (
                stream.read(1) * run_len if code & 1 else stream.read(run_len)
            )
            buffer += run_line

    if decoded_size and len(buffer) != decoded_size:
        raise UnexpectedBufferSize(decoded_size, len(buffer), buffer)

    return bytes(buffer)
