# Stubs for PIL.GifImagePlugin (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from PIL import ImageFile
from typing import Any, Optional

i8: Any
i16: Any
o8: Any
o16: Any

class GifImageFile(ImageFile.ImageFile):
    format: str = ...
    format_description: str = ...
    global_palette: Any = ...
    def data(self): ...
    @property
    def n_frames(self): ...
    @property
    def is_animated(self): ...
    def seek(self, frame: Any) -> None: ...
    def tell(self): ...
    im: Any = ...
    def load_end(self) -> None: ...

RAWMODE: Any

def get_interlace(im: Any): ...
def getheader(im: Any, palette: Optional[Any] = ..., info: Optional[Any] = ...): ...
def getdata(im: Any, offset: Any = ..., **params: Any): ...
