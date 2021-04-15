import glob
import os
from pathlib import Path

import typer

from nutcracker.sputm2.build import rebuild_resources, update_element
from nutcracker.sputm2.schema import SCHEMA
from nutcracker.sputm2.strings import (
    get_all_scripts,
    get_optable,
    get_script_map,
    msg_to_print,
    print_to_msg,
    update_element_strings,
)
from nutcracker.sputm2.tree import dump_resources, narrow_schema, open_game_resource

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

    updated_resource = list(update_element(dirname, gameres.root, files))
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

    with open(textfile, 'w') as f:
        for msg in get_all_scripts(root, script_ops, script_map):
            print(msg_to_print(msg), file=f)


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


if __name__ == "__main__":
    app()
