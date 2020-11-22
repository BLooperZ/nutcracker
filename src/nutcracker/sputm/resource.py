import glob
import os
import itertools
from dataclasses import dataclass
from typing import Sequence, Callable

from parse import parse

from nutcracker.sputm.index import read_index_v8, read_index_v5tov7, read_index_he, read_file, read_directory_leg as read_dir, read_dlfl

@dataclass(frozen=True)
class GameResourceConfig:
    resources: Sequence[str]
    read_index: Callable
    chiper_key: int
    max_depth: int


def detect_resource(path):
    resources = glob.glob(f'{path}.*')
    if os.path.exists(f'{path}.000'):
        # Configuration for SCUMM v5-v6 games
        pattern = '.{i:03d}'
        resources = [res for res in resources if parse(f'{path}{pattern}', res, evaluate_result=False)]
        read_index = read_index_v5tov7
        chiper_key = 0x69
        max_depth = 4
        return GameResourceConfig(resources, read_index, chiper_key, max_depth)

    if os.path.exists(f'{path}.HE0'):
        # Configuration for HE games
        pattern = '.HE{i:d}'
        resources = [res for res in resources if parse(f'{path}{pattern}', res, evaluate_result=False)][:2]
        if os.path.exists(f'{path}.(a)'):
            resources = [resources[0], f'{path}.(a)']
        read_index = read_index_he
        chiper_key = 0x69
        max_depth = 4
        return GameResourceConfig(resources, read_index, chiper_key, max_depth)

    if os.path.exists(f'{path}.LA0'):
        # Configuration for SCUMM v7 games
        pattern = '.LA{i:d}'
        resources = [res for res in resources if parse(f'{path}{pattern}', res, evaluate_result=False)]
        read_index = read_index_v8
        chiper_key = 0x00
        max_depth = 3
        return GameResourceConfig(resources, read_index, chiper_key, max_depth)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    args = parser.parse_args()

    print(detect_resource(args.filename))
