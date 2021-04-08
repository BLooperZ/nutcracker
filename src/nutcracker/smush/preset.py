from nutcracker.kernel import settings, preset

from .schema import SCHEMA

smush = preset.shell(align=2, chunk=settings.IFF_CHUNK_EX, schema=SCHEMA)
