
import numpy as np


def decode1(width, height, num_colors, stream, strict=True):

    masks = {16: (4, 0x0F), 32: (3, 0x07), 64: (2, 0x03)}
    shift, mask = masks[num_colors]

    out = bytearray()
    decoded_size = width * height

    try:
        while len(out) < decoded_size:
            rep = stream.read(1)[0]
            color = rep >> shift
            rep &= mask
            if rep == 0:
                rep = stream.read(1)[0]
            out += bytes([color]) * rep

        return np.frombuffer(out[:decoded_size], dtype=np.uint8).reshape(
            (height, width), order='F'
        )

    except IndexError:
        if strict:
            raise
        out += b'\0' * (decoded_size - len(out))
        return np.frombuffer(out[:decoded_size], dtype=np.uint8).reshape(
            (height, width), order='F'
        )
