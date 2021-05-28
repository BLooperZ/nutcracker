import glob
import os
from pathlib import Path
from typing import Iterable, List, Set

import typer

from nutcracker.smush import anim
from nutcracker.smush.compress import strip_compress_san
from nutcracker.smush.decode import decode_nut, decode_san
from nutcracker.smush.preset import smush
from nutcracker.sputm.room.orgroom import make_room_images_patch
from nutcracker.sputm.room.pproom import extract_room_images
from nutcracker.utils.fileio import write_file
from nutcracker.utils.funcutils import flatten

from ..tree import open_game_resource, narrow_schema
from ..schema import SCHEMA

app = typer.Typer()


@app.command('decode')
def decode(
    filename: Path = typer.Argument(..., help='Game resource index file'),
    ega_mode: bool = typer.Option(False, '--ega', help='Simulate EGA images decoding'),
) -> None:
    gameres = open_game_resource(filename)
    basename = gameres.basename

    root = gameres.read_resources(
        # schema=narrow_schema(
        #     SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'PALS'}
        # )
    )

    rnam = gameres.rooms
    version = gameres.game.version

    basedir = os.path.join(basename, 'IMAGES')
    os.makedirs(basedir, exist_ok=True)

    os.makedirs(os.path.join(basedir, 'backgrounds'), exist_ok=True)
    os.makedirs(os.path.join(basedir, 'objects'), exist_ok=True)
    os.makedirs(os.path.join(basedir, 'objects_layers'), exist_ok=True)

    extract_room_images(root, basedir, rnam, version, ega_mode=ega_mode)


@app.command('encode')
def encode(
    dirname: Path = typer.Argument(..., help='Patch directory'),
    ref: Path = typer.Option(..., '--ref', help='Reference resource index'),
) -> None:
    gameres = open_game_resource(ref)
    basename = os.path.basename(os.path.normpath(dirname))

    print(f'Creating patch images for: {basename}')

    root = gameres.read_resources(
        # schema=narrow_schema(
        #     SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'PALS'}
        # )
    )

    for path, content in make_room_images_patch(
        root,
        os.path.join(basename, 'IMAGES'),
        gameres.rooms,
        gameres.game.version
    ):
        res_path = os.path.join(dirname, path)
        os.makedirs(os.path.dirname(res_path), exist_ok=True)
        write_file(res_path, content)


if __name__ == '__main__':
    app()
