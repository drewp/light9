# Stubs for PIL.GdImageFile (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import __builtin__
from PIL import ImageFile
from typing import Any

builtins = __builtin__
i16: Any

class GdImageFile(ImageFile.ImageFile):
    format: str = ...
    format_description: str = ...

def open(fp: Any, mode: str = ...): ...
