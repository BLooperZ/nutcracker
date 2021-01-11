from typing import IO, Optional

CHIPER_KEY = 0x69


def read(stream: IO[bytes], size: Optional[int] = None, key: int = CHIPER_KEY) -> bytes:
    # None reads until EOF
    return bytes(b ^ key for b in stream.read(size))  # type: ignore


def write(stream: IO[bytes], data: bytes, key: int = CHIPER_KEY) -> int:
    return stream.write(bytes(b ^ key for b in data))


if __name__ == '__main__':
    import argparse
    from functools import partial

    from nutcracker.utils import copyio

    parser = argparse.ArgumentParser(description='read smush file')
    parser.add_argument('filename', help='filename to read from')
    parser.add_argument('output', help='filename to read from')
    parser.add_argument('-c', '--chiper-key', default='0x69', type=str, help='xor key')
    args = parser.parse_args()

    with open(args.filename, 'rb') as infile, open(args.output, 'wb') as outfile:
        for buffer in copyio.buffered(
            partial(read, infile, key=int(args.chiper_key, 16))
        ):
            outfile.write(buffer)
