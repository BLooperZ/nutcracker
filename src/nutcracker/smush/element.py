from typing import Iterator

from .types import Element


def check_tag(target: str, elem: Element) -> Element:
    if elem.tag != target:
        raise ValueError(f'expected tag to be {target} but got {elem.tag}')
    return elem


def read_elements(target: str, elem: Element) -> Iterator[Element]:
    return iter(check_tag(target, elem).children)


def read_data(target: str, elem: Element) -> bytes:
    return check_tag(target, elem).data
