import glob
import os
import pathlib
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from nutcracker.kernel2.element import Element
from nutcracker.kernel2.fileio import ResourceFile

from .index import read_directory_leg, read_directory_leg_v8
from .preset import sputm

version_by_ext_maxs = {
    ('.LA0', 176): (8, 0),
    ('.LA0', 138): (7, 0),
    ('.000', 138): (7, 0),
    ('.HE0', 52): (6, 99),  # (6, 100), (6, 101)
    ('.HE0', 46): (6, 90),  # (6, 90), (6, 98)
    ('.HE0', 40): (6, 80),  # (6, 72), (6, 73), (6, 80),
    ('.HE0', 38): (6, 71),  # (6, 60), (6, 70), (6, 71),
    ('.000', 38): (6, 0),
    ('.SM0', 38): (6, 0),
    ('.000', 26): (5, 0),
    ('.LFL', 26): (5, 0),
}

chiper_keys = {
    '.000': 0x69,
    '.SM0': 0x69,
    '.HE0': 0x69,
    '.LA0': 0x00,
}


@dataclass
class _GameMeta:
    basedir: str
    basename: str
    ext: str
    version: int
    he_version: int
    chiper_key: int


@dataclass
class Game(_GameMeta):
    index: Sequence[Element] = field(repr=False)
    disks: Sequence[str] = field(repr=False)


def get_disk(game: _GameMeta, num: int) -> str:
    if game.ext == '.000':
        return f'{game.basename}.{num:03d}'
    if game.ext == '.SM0':
        return f'{game.basename}.SM{num:d}'
    if game.ext == '.HE0':
        if game.he_version >= 98 and num > 0:
            ext = f'({chr(ord('`') + num)})'
            if num > 1:
                # Special names for Blue's
                base = game.basename.split('-')[0]
                return f'{base}.{ext}'
            return f'{game.basename}.{ext}'
        return f'{game.basename}.HE{num:d}'
    if game.ext == '.LA0':
        return f'{game.basename}.LA{num:d}'
    assert game.ext == '.LFL'
    return f'DISK{num:02d}.LEC' if num > 0 else '000.LFL'


def load_index(index_file: str | os.PathLike[str], chiper_key: int = 0) -> Sequence[Element]:
    with ResourceFile.load(index_file, key=chiper_key) as index:
        schema = sputm.generate_schema(index)
        index_root = list(sputm(schema=schema).map_chunks(index))
    return index_root

class IndexFileExpectedError(FileNotFoundError):
    """Exception raised when a file is expected but a directory is found."""
    def __init__(self, message: str, path: str | os.PathLike[str]) -> None:
        self.basedir = pathlib.Path(path)
        suggestions = self.find_suggestions()
        if suggestions:
            message += f' Suggested files: {", ".join(str(s) for s in suggestions)}'
        super().__init__(message)

    def find_suggestions(self) -> list[pathlib.Path]:
        """Return a list of suggested files based on the directory."""
        valid_globs = {'*.000', '*.LA0', '*.HE0', '*.SM0', '000.LFL'}
        suggestions: list[pathlib.Path] = []
        for valglob in valid_globs:
            suggestions.extend(path for path in pathlib.Path(self.basedir).glob(valglob))
        return suggestions


def load_resource(index_file: str | os.PathLike[str], chiper_key: int | None = None) -> Game:
    print(index_file)
    if pathlib.Path(index_file).is_dir():
        raise IndexFileExpectedError(
            f'Expected file, but got directory: {index_file}',
            index_file,
        )
    basename, ext = os.path.splitext(os.path.basename(index_file))
    ext = ext.upper()
    basedir = os.path.dirname(index_file)

    if chiper_key is None:
        chiper_key = chiper_keys.get(ext, 0x00)

    try:
        index_root = load_index(index_file, chiper_key)
    except FileNotFoundError as exc:
        # suggest index files by prefix in same directory
        valid_globs = {'*.000', '*.LA0', '*.HE0', '*.SM0', '000.LFL'}
        suggestions = []
        if pathlib.Path(index_file).is_dir():
            basedir = index_file
        suggestions.extend(
            path for valglob in valid_globs for path in pathlib.Path(basedir).glob(valglob)
        )
        # suggest the files if found
        raise IndexFileExpectedError(
            f'File not found: {index_file}',
            basedir,
        ) from exc
    # Detect version from index
    maxs = sputm.find('MAXS', index_root)
    version, he_version = version_by_ext_maxs[(ext, len(maxs.data) + 8)]
    if sputm.find('INIB', index_root):
        assert he_version >= 90
        he_version = max(98, he_version)
    if 0 < he_version < 72 and sputm.find('DROO', index_root):
        he_version = 60
    # TODO: can diffenetiate he80 from he72 by size of RNAM?

    room_pattern = '{room:03d}.LFL'  # noqa: F841

    if ext == '.LFL':
        basename = os.path.basename(basedir)

    disk_elem = sputm.find('DROO', index_root) or sputm.find('DISK', index_root)
    read_dir = read_directory_leg_v8 if version == 8 else read_directory_leg

    disk_data = read_dir(disk_elem.data) if disk_elem else ((0, (0, 0)), (1, (1, 0)))

    disks = sorted(set(disk for _room_id, (disk, _) in disk_data))

    game = _GameMeta(basedir, basename, ext, version, he_version, chiper_key)

    return Game(
        **(asdict(game)),
        index=index_root,
        disks=tuple(get_disk(game, disk) for disk in disks),
    )


if __name__ == '__main__':
    import argparse

    from nutcracker.utils.funcutils import flatten

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('files', nargs='+', help='files to read from')
    args = parser.parse_args()

    files = set(flatten(glob.iglob(r) for r in args.files))
    print(files)
    for filename in files:
        print(load_resource(filename))
