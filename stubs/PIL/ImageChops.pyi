# Stubs for PIL.ImageChops (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

def constant(image: Any, value: Any): ...
def duplicate(image: Any): ...
def invert(image: Any): ...
def lighter(image1: Any, image2: Any): ...
def darker(image1: Any, image2: Any): ...
def difference(image1: Any, image2: Any): ...
def multiply(image1: Any, image2: Any): ...
def screen(image1: Any, image2: Any): ...
def add(image1: Any, image2: Any, scale: float = ..., offset: int = ...): ...
def subtract(image1: Any, image2: Any, scale: float = ..., offset: int = ...): ...
def add_modulo(image1: Any, image2: Any): ...
def subtract_modulo(image1: Any, image2: Any): ...
def logical_and(image1: Any, image2: Any): ...
def logical_or(image1: Any, image2: Any): ...
def logical_xor(image1: Any, image2: Any): ...
def blend(image1: Any, image2: Any, alpha: Any): ...
def composite(image1: Any, image2: Any, mask: Any): ...
def offset(image: Any, xoffset: Any, yoffset: Optional[Any] = ...): ...
