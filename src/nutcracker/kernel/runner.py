import argparse
import os
from dataclasses import replace
from pprint import pprint
from typing import Dict, Optional

import yaml

from nutcracker.kernel.chunk import Chunk
from nutcracker.kernel.element import Element
from nutcracker.utils.fileio import read_file

from . import index, settings, tree
from .chunk import SizeFixedChunk

HEX_BASE = 16

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('--size-fix', default=0, type=int, help='header size fix')
    parser.add_argument('--align', default=1, type=int, help='alignment between chunks')
    parser.add_argument('--schema', type=str, help='load saved schema from file')
    parser.add_argument('--chiper-key', default='0x00', type=str, help='xor key')
    parser.add_argument('--max-depth', default=None, type=int, help='max depth')
    parser.add_argument('--schema-dump', type=str, help='save schema to file')
    args = parser.parse_args()

    cfg = settings._IndexSetting(
        chunk=SizeFixedChunk(
            settings.IFF_CHUNK_HEADER,
            size_fix=args.size_fix,
        ),
        align=args.align,
        max_depth=args.max_depth,
    )

    schema = None
    if args.schema:
        with open(args.schema, 'r') as schema_in:
            schema = yaml.safe_load(schema_in)

    data = read_file(args.filename, key=int(args.chiper_key, HEX_BASE))

    schema = schema or index.generate_schema(cfg, data)

    pprint(schema)

    if args.schema_dump:
        with open(args.schema_dump, 'w') as schema_out:
            yaml.dump(schema, schema_out)

    def update_element_path(
        parent: Optional[Element],
        chunk: Chunk,
        offset: int,
    ) -> Dict[str, str]:
        dirname = parent.attribs['path'] if parent else ''
        return {'path': os.path.join(dirname, chunk.tag)}

    root = index.map_chunks(
        replace(cfg, schema=schema),
        data,
        extra=update_element_path,
    )
    for elem in root:
        tree.render(elem)
