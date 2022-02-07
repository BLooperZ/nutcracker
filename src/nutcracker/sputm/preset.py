from pytest import skip
from nutcracker.kernel import preset, settings

from .schema import SCHEMA

sputm = preset.shell(align=1, chunk=settings.IFF_CHUNK_IN, schema=SCHEMA, skip_byte=0x80)
