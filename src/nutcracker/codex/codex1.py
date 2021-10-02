import io
import itertools

import numpy as np


from nutcracker.codex import base, bomp



def encode1(bmap):
    return bomp.encode_image(bmap)


PARAMS = [
    (3, False, 1),  # SAMNMAX/ROOMS-BOMP, COMI/ROOMS-BOMP, FT/ROOMS-BOMP, DIG/ROOMS-BOMP  # FT/ICONS2.NUT
    (3, False, 0),  # FT/ROOMS-BOMP(*)
    (4, True, 1),  # FT/ICONS.NUT, FT/BENCUT.NUT, FT/BENSGOGG.NUT
]


def decode1(width, height, f):
    BG = 39

    # print(mat)
    mat = bomp.decode_image(f, width, height)


    with io.BytesIO(f) as stream:
        lines = [base.unwrap_uint16le(stream) for _ in range(height)]
    print([list(bomp.iter_decode(line)) for line in lines])

    g = [[
        list(group)
        for c, group in itertools.groupby(line)
    ] for line in mat]


    encs = []

    for limit, carry, end_limit in PARAMS:
        encs.append(bomp.encode_image(mat, limit=limit, carry=carry, end_limit=end_limit))
        print(list(list(bomp.encode_groups(l, limit=limit, carry=carry, end_limit=end_limit)) for l in g))

    assert any(x == f[:len(x)] for x in encs), (encs, f)

    mat = np.where(mat==0, BG, mat)
    return mat
