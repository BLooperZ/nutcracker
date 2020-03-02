from nutcracker.kernel import settings, preset

from .schema import SCHEMA

smush = preset.shell(align=2, size_fix=settings.EXCLUSIVE, schema=SCHEMA)
