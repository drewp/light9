# Stubs for PIL.PcdImagePlugin (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from PIL import ImageFile
from typing import Any

i8: Any

class PcdImageFile(ImageFile.ImageFile):
    format: str = ...
    format_description: str = ...
    im: Any = ...
    size: Any = ...
    def load_end(self) -> None: ...
