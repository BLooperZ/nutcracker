from nutcracker.chiper import xor


def read_file(path: str, key: int = 0x00) -> bytes:
    with open(path, 'rb') as res:
        return xor.read(res, key=key)


def write_file(path: str, data: bytes, key: int = 0x00) -> int:
    with open(path, 'wb') as res:
        return xor.write(res, data, key=key)
