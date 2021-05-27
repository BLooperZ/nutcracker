import glob
import os
from pathlib import Path

import typer

from nutcracker.sputm.build import rebuild_resources, update_element
from nutcracker.sputm.char.decode import decode_all_fonts, get_chars
from nutcracker.sputm.char.encode import encode_char
from nutcracker.sputm.schema import SCHEMA
from nutcracker.sputm.strings import (
    get_all_scripts,
    get_optable,
    get_script_map,
    msg_to_print,
    print_to_msg,
    update_element_strings,
)
from nutcracker.sputm.tree import dump_resources, narrow_schema, open_game_resource
from nutcracker.utils.fileio import write_file
from .preset import sputm

app = typer.Typer()


# ## RESOURCE


@app.command()
def extract(
    filename: Path = typer.Argument(..., help='Game resource index file'),
) -> None:
    gameres = open_game_resource(filename)
    basename = gameres.basename
    print(f'Extracting game resources: {basename}')
    dump_resources(gameres, basename)


@app.command()
def build(
    dirname: Path = typer.Argument(..., help='Patch directory'),
    ref: Path = typer.Option(..., '--ref', help='Reference resource index'),
) -> None:
    gameres = open_game_resource(ref)
    basename = os.path.basename(os.path.normpath(dirname))
    print(f'Rebuilding game resources: {basename}')

    files = set(glob.iglob(f'{dirname}/**/*', recursive=True))
    assert None not in files

    root = gameres.read_resources(
        # schema=narrow_schema(
        #     SCHEMA, {'LECF', 'LFLF', 'ROOM', 'RMIM'}
        # )
    )

    updated_resource = list(update_element(dirname, root, files))
    rebuild_resources(gameres, basename, updated_resource)


# ## STRINGS


@app.command('strings_extract')
def extract_strings(
    filename: Path = typer.Argument(..., help='Game resource index file'),
    textfile: Path = typer.Option(
        'strings.txt', "--textfile", "-t", help='save strings to file'
    ),
) -> None:
    gameres = open_game_resource(filename)
    basename = os.path.basename(os.path.normpath(filename))
    print(f'Extracting strings from game resources: {basename}')

    script_ops = get_optable(gameres.game)
    script_map = get_script_map(gameres.game)

    root = gameres.read_resources(
        schema=narrow_schema(
            SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map}
        )
    )

    var_size = 4 if gameres.game.version >= 8 else 2

    with open(textfile, 'w') as f:
        for msg in get_all_scripts(root, script_ops, script_map):
            print(msg_to_print(msg, var_size=var_size), file=f)


@app.command('strings_inject')
def inject_strings(
    filename: Path = typer.Argument(..., help='Game resource index file'),
    textfile: Path = typer.Option(
        'strings.txt', "--textfile", "-t", help='save strings to file'
    ),
) -> None:
    gameres = open_game_resource(filename)
    basename = gameres.basename
    print(f'Injecting strings into game resources: {basename}')

    script_ops = get_optable(gameres.game)
    script_map = get_script_map(gameres.game)

    root = gameres.read_resources(
        schema=narrow_schema(
            SCHEMA, {'LECF', 'LFLF', 'RMDA', 'ROOM', 'OBCD', *script_map}
        )
    )

    with open(textfile, 'r') as f:
        fixed_lines = (print_to_msg(line) for line in f)
        updated_resource = list(
            update_element_strings(root, fixed_lines, script_ops, script_map)
        )

    rebuild_resources(gameres, basename, updated_resource)


# ## FONTS


@app.command('fonts_extract')
def extract_fonts(
    filename: Path = typer.Argument(..., help='Game resource index file'),
) -> None:
    gameres = open_game_resource(filename)
    basename = gameres.basename
    print(f'Extracting fonts from game resources: {basename}')

    root = gameres.read_resources(
        schema=narrow_schema(SCHEMA, {'LECF', 'LFLF', 'CHAR'})
    )

    outdir = os.path.join(basename, 'chars')
    os.makedirs(outdir, exist_ok=True)

    for fname, bim in decode_all_fonts(root):
        bim.save(os.path.join(outdir, f'{fname}.png'))
        print(f'saved {basename}-{fname}.png')


@app.command('fonts_inject')
def inject_fonts(
    dirname: Path = typer.Argument(..., help='Patch directory'),
    ref: Path = typer.Option(..., '--ref', help='Reference resource index'),
) -> None:
    gameres = open_game_resource(ref)
    basename = os.path.basename(os.path.normpath(dirname))
    print(f'Creating path for game fonts: {basename}')

    root = gameres.read_resources(
        schema=narrow_schema(SCHEMA, {'LECF', 'LFLF', 'CHAR'})
    )

    base = os.path.join(dirname, 'chars')

    for elem in get_chars(root):
        path = elem.attribs['path']
        fname = os.path.basename(path)
        patch_file = os.path.join(base, f'{fname}.png')
        if os.path.exists(patch_file):
            base_out = os.path.join(dirname, path)
            os.makedirs(os.path.dirname(base_out), exist_ok=True)
            write_file(
                base_out,
                sputm.mktag('CHAR', encode_char(elem, patch_file))
            )


if __name__ == "__main__":
    app()
