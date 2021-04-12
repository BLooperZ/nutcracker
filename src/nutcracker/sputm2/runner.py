import glob
import os
from pathlib import Path

import typer

from nutcracker.sputm2.build import rebuild_resources, update_element
from nutcracker.sputm2.tree import dump_resources, open_game_resource

app = typer.Typer()


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


if __name__ == "__main__":
    app()
