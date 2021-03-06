# Stubs for PIL.ImageMorph (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

LUT_SIZE: Any

class LutBuilder:
    patterns: Any = ...
    lut: Any = ...
    def __init__(self, patterns: Optional[Any] = ..., op_name: Optional[Any] = ...) -> None: ...
    def add_patterns(self, patterns: Any) -> None: ...
    def build_default_lut(self) -> None: ...
    def get_lut(self): ...
    def build_lut(self): ...

class MorphOp:
    lut: Any = ...
    def __init__(self, lut: Optional[Any] = ..., op_name: Optional[Any] = ..., patterns: Optional[Any] = ...) -> None: ...
    def apply(self, image: Any): ...
    def match(self, image: Any): ...
    def get_on_pixels(self, image: Any): ...
    def load_lut(self, filename: Any) -> None: ...
    def save_lut(self, filename: Any) -> None: ...
    def set_lut(self, lut: Any) -> None: ...
