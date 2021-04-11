#!/usr/bin/env python3
from .codex1 import decode1, encode1
from .codex37_np import decode37 as e_decode37
from .codex37_np import fake_encode37
from .codex47_np import decode47 as e_decode47
from .codex47_np import fake_encode47
from .nutfont import codec21, codec44, unidecoder

# DECODE

encode1 = encode1


def decode47(width, height, f):
    return e_decode47(f, width, height)


def decode37(width, height, f):
    return e_decode37(f, width, height)


decoders = {
    1: decode1,
    21: unidecoder,
    44: unidecoder,
    47: decode47,
    37: decode37,
}


def get_decoder(codec):
    if codec in decoders:
        return decoders[codec]
    return NotImplemented


# ENCODE

encoders = {
    21: codec21,
    44: codec44,
    37: fake_encode37,
    47: fake_encode47,
}


def get_encoder(codec):
    if codec in encoders:
        return encoders[codec]
    print(codec)
    return NotImplemented
