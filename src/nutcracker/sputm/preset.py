from nutcracker.kernel import settings, preset

from .schema import SCHEMA

sputm = preset.shell(align=1, chunk=settings.IFF_CHUNK_IN, schema=SCHEMA)
