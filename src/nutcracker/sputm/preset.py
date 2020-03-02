#!/usr/bin/env python3

from nutcracker.kernel import settings
from nutcracker.kernel.preset import shell

from .schema import SCHEMA

sputm = shell(align=1, size_fix=settings.INCLUSIVE, schema=SCHEMA)
