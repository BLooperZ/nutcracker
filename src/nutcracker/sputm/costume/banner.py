import glob
import pathlib
import struct
import typer
from typing import List

import numpy as np
from PIL import Image
from nutcracker.codex.rle import encode_lined_rle
from nutcracker.sputm.costume.awiz import read_awiz_resource
from nutcracker.sputm.preset import sputm
from nutcracker.sputm.room.orgroom import make_wrap
from nutcracker.utils.funcutils import flatten
from nutcracker.utils.fileio import read_file, write_file


app = typer.Typer()


@app.command()
def decode(
    files: List[str] = typer.Argument(..., help='*.wiz files to read from'),
) -> None:
    files = sorted(set(flatten(glob.iglob(r) for r in files)))
    for filename in files:

        chunks = list(sputm.map_chunks(read_file(filename)))

        for chunk in chunks:
            sputm.render(chunk)

            if chunk.tag == 'MULT':
                wrap = sputm.find('WRAP', chunk)
                defa = sputm.find('DEFA', chunk)
                rgbs = sputm.find('RGBS', defa)
                assert wrap
                assert defa
                assert rgbs
                for awiz in wrap.children[1:]:
                    im = read_awiz_resource(awiz, rgbs.data)
                    im.save(f'{pathlib.Path(filename).stem}.png')


@app.command()
def encode(
    files: List[str] = typer.Argument(..., help='*.png files to read from'),
) -> None:
    files = sorted(set(flatten(glob.iglob(r) for r in files)))
    for filename in files:

        im = Image.open(filename)
        width, height = im.size
        palette = bytes(im.getpalette())
        encoded = encode_lined_rle(np.asarray(im))

        defa = sputm.mktag('DEFA', sputm.mktag('RGBS', palette))
        wizh = struct.pack('<3I', 1, width, height)
        awiz = sputm.untag(
            sputm.mktag(
                'AWIZ',
                sputm.write_chunks(
                    [
                        sputm.mktag('WIZH', wizh),
                        sputm.mktag('SPOT', b'\xbf\x00\x00\x00Q\xff\xff\xff'),
                        sputm.mktag('WIZD', encoded),
                    ],
                ),
            )
        )
        wrap = make_wrap(
            [(awiz, awiz.data)],
        )
        write_file(
            f'{pathlib.Path(filename).stem}.wiz',
            sputm.mktag('MULT', sputm.write_chunks([defa, wrap])),
        )


if __name__ == '__main__':
    app()
