def read(fields, structure, stream):
    values = structure.unpack(stream.read(structure.size))
    return dict(zip(fields, values))
