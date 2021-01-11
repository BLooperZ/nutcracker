import io
import os
import sys
from typing import IO, Iterator, Optional

from parse import parse

from .types import Element, ElementTree


def findall(tag: str, root: ElementTree) -> Iterator[Element]:
    if not root:
        return
    for c in root:
        if parse(tag, c.tag, evaluate_result=False):
            yield c


def find(tag: str, root: ElementTree) -> Optional[Element]:
    return next(findall(tag, root), None)


def findpath(path: str, root: Optional[Element]) -> Optional[Element]:
    path = os.path.normpath(path)
    if not path or path == '.':
        return root
    dirname, basename = os.path.split(path)
    return find(basename, findpath(dirname, root))


def render(
    element: Optional[Element], level: int = 0, stream: IO[str] = sys.stdout
) -> None:
    if not element:
        return
    attribs = ''.join(
        f' {key}="{value}"'
        for key, value in element.attribs.items()
        if value is not None
    )
    indent = '    ' * level
    closing = '' if element.children else ' /'
    print(f'{indent}<{element.tag}{attribs}{closing}>', file=stream)
    if element.children:
        for c in element.children:
            render(c, level=level + 1, stream=stream)
        print(f'{indent}</{element.tag}>', file=stream)


def renders(element: Optional[Element]) -> str:
    with io.StringIO() as stream:
        render(element, stream=stream)
        return stream.getvalue()
