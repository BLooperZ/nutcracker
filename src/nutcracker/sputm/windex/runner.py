import functools
import os
from pathlib import Path

import typer

from ..preset import sputm
from ..tree import open_game_resource, narrow_schema
from ..schema import SCHEMA
from ..script.bytecode import script_map

from .scu import dump_script_file
from .. import windex_v5, windex_v6

app = typer.Typer()


@app.command('decompile')
def decompile(
    filename: Path = typer.Argument(..., help='Game resource index file'),
    verbose: bool = typer.Option(False, '--verbose', help='Dump each opcode for debug'),
) -> None:
    gameres = open_game_resource(filename)
    basename = gameres.basename

    root = gameres.read_resources(
        max_depth=5,
        schema=narrow_schema(
            SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map}
        ),
    )

    rnam = gameres.rooms
    print(gameres.game)
    print(rnam)

    script_dir = os.path.join('scripts', basename)
    os.makedirs(script_dir, exist_ok=True)

    if gameres.game.version >= 6:
        decompile = functools.partial(
            windex_v6.decompile_script,
            game=gameres.game,
            verbose=verbose,
        )
    elif gameres.game.version >= 5:
        decompile = windex_v5.decompile_script

    for disk in root:
        for room in sputm.findall('LFLF', disk):
            room_no = rnam.get(room.attribs['gid'], f"room_{room.attribs['gid']}")
            print(
                '==========================',
                room.attribs['path'],
                room_no,
            )
            fname = f"{script_dir}/{room.attribs['gid']:04d}_{room_no}.scu"

            with open(fname, 'w', encoding='windows-1255', errors='ignore') as script_file:
                dump_script_file(room_no, room, decompile, script_file)


if __name__ == '__main__':
    app()
