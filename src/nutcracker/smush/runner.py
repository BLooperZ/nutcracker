import glob
import os
from typing import Iterable, List, Set

import typer

from nutcracker.smush import anim
from nutcracker.smush.compress import strip_compress_san
from nutcracker.smush.decode import decode_nut, decode_san
from nutcracker.smush.preset import smush
from nutcracker.utils.fileio import write_file
from nutcracker.utils.funcutils import flatten

app = typer.Typer()


def get_files(globs: Iterable[str]) -> Set[str]:
    return set(flatten(glob.iglob(fname) for fname in globs))


@app.command('map')
def map_elements(
    files: List[str] = typer.Argument(..., help='Files to read from'),
) -> None:
    for filename in get_files(files):
        basename = os.path.basename(filename)
        print(f'Mapping file: {basename}')
        root = anim.from_path(filename)
        smush.render(root)


@app.command('decode')
def decode(
    files: List[str] = typer.Argument(..., help='Files to read from'),
    nut: bool = typer.Option(False, '--nut', help='Decode to grid image'),
    target_dir: str = typer.Option('out', '--target', '-t', help='Target directory'),
) -> None:
    for filename in get_files(files):
        basename = os.path.basename(filename)
        print(f'Decoding file: {basename}')
        root = anim.from_path(filename)
        output_dir = os.path.join(target_dir, basename)
        if nut:
            decode_nut(root, output_dir)
        else:
            decode_san(root, output_dir)


@app.command('compress')
def compress(
    files: List[str] = typer.Argument(..., help='Files to read from'),
    target_dir: str = typer.Option('out', '--target', '-t', help='Target directory'),
) -> None:
    for filename in get_files(files):
        basename = os.path.basename(filename)
        print(f'Compressing file: {basename}')
        root = anim.from_path(filename)
        output = os.path.join(target_dir, basename)
        compressed = strip_compress_san(root)
        os.makedirs(target_dir, exist_ok=True)
        write_file(output, compressed)


if __name__ == '__main__':
    app()
