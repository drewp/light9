# Stubs for PIL.Image (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

logger: Any

class DecompressionBombWarning(RuntimeWarning): ...

class _imaging_not_installed:
    def __getattr__(self, id: Any) -> None: ...

MAX_IMAGE_PIXELS: Any
USE_CFFI_ACCESS: Any
HAS_CFFI: bool

def isImageType(t: Any): ...

NONE: int
FLIP_LEFT_RIGHT: int
FLIP_TOP_BOTTOM: int
ROTATE_90: int
ROTATE_180: int
ROTATE_270: int
TRANSPOSE: int
AFFINE: int
EXTENT: int
PERSPECTIVE: int
QUAD: int
MESH: int
NEAREST: int
BOX: int
BILINEAR: int
LINEAR: int
HAMMING: int
BICUBIC: int
CUBIC: int
LANCZOS: int
ANTIALIAS: int
ORDERED: int
RASTERIZE: int
FLOYDSTEINBERG: int
WEB: int
ADAPTIVE: int
MEDIANCUT: int
MAXCOVERAGE: int
FASTOCTREE: int
LIBIMAGEQUANT: int
NORMAL: int
SEQUENCE: int
CONTAINER: int
DEFAULT_STRATEGY: Any
FILTERED: Any
HUFFMAN_ONLY: Any
RLE: Any
FIXED: Any
ID: Any
OPEN: Any
MIME: Any
SAVE: Any
SAVE_ALL: Any
EXTENSION: Any
MODES: Any

def getmodebase(mode: Any): ...
def getmodetype(mode: Any): ...
def getmodebandnames(mode: Any): ...
def getmodebands(mode: Any): ...
def preinit() -> None: ...
def init(): ...
def coerce_e(value: Any): ...

class _E:
    data: Any = ...
    def __init__(self, data: Any) -> None: ...
    def __add__(self, other: Any): ...
    def __mul__(self, other: Any): ...

class Image:
    format: Any = ...
    format_description: Any = ...
    im: Any = ...
    mode: str = ...
    size: Any = ...
    palette: Any = ...
    info: Any = ...
    category: Any = ...
    readonly: int = ...
    pyaccess: Any = ...
    def __init__(self) -> None: ...
    @property
    def width(self): ...
    @property
    def height(self): ...
    def __enter__(self): ...
    def __exit__(self, *args: Any) -> None: ...
    def close(self) -> None: ...
    def __eq__(self, other: Any): ...
    def __ne__(self, other: Any): ...
    @property
    def __array_interface__(self): ...
    def tobytes(self, encoder_name: str = ..., *args: Any): ...
    def tostring(self, *args: Any, **kw: Any) -> None: ...
    def tobitmap(self, name: str = ...): ...
    def frombytes(self, data: Any, decoder_name: str = ..., *args: Any) -> None: ...
    def fromstring(self, *args: Any, **kw: Any) -> None: ...
    def load(self): ...
    def verify(self) -> None: ...
    def convert(self, mode: Optional[Any] = ..., matrix: Optional[Any] = ..., dither: Optional[Any] = ..., palette: Any = ..., colors: int = ...): ...
    def quantize(self, colors: int = ..., method: Optional[Any] = ..., kmeans: int = ..., palette: Optional[Any] = ...): ...
    def copy(self): ...
    __copy__: Any = ...
    def crop(self, box: Optional[Any] = ...): ...
    def draft(self, mode: Any, size: Any) -> None: ...
    def filter(self, filter: Any): ...
    def getbands(self): ...
    def getbbox(self): ...
    def getcolors(self, maxcolors: int = ...): ...
    def getdata(self, band: Optional[Any] = ...): ...
    def getextrema(self): ...
    def getim(self): ...
    def getpalette(self): ...
    def getpixel(self, xy: Any): ...
    def getprojection(self): ...
    def histogram(self, mask: Optional[Any] = ..., extrema: Optional[Any] = ...): ...
    def offset(self, xoffset: Any, yoffset: Optional[Any] = ...) -> None: ...
    def paste(self, im: Any, box: Optional[Any] = ..., mask: Optional[Any] = ...) -> None: ...
    def point(self, lut: Any, mode: Optional[Any] = ...): ...
    def putalpha(self, alpha: Any) -> None: ...
    def putdata(self, data: Any, scale: float = ..., offset: float = ...) -> None: ...
    def putpalette(self, data: Any, rawmode: str = ...) -> None: ...
    def putpixel(self, xy: Any, value: Any): ...
    def resize(self, size: Any, resample: Any = ...): ...
    def rotate(self, angle: Any, resample: Any = ..., expand: int = ..., center: Optional[Any] = ..., translate: Optional[Any] = ...): ...
    encoderinfo: Any = ...
    encoderconfig: Any = ...
    def save(self, fp: Any, format: Optional[Any] = ..., **params: Any) -> None: ...
    def seek(self, frame: Any) -> None: ...
    def show(self, title: Optional[Any] = ..., command: Optional[Any] = ...) -> None: ...
    def split(self): ...
    def tell(self): ...
    def thumbnail(self, size: Any, resample: Any = ...) -> None: ...
    def transform(self, size: Any, method: Any, data: Optional[Any] = ..., resample: Any = ..., fill: int = ...): ...
    def transpose(self, method: Any): ...
    def effect_spread(self, distance: Any): ...
    def toqimage(self): ...
    def toqpixmap(self): ...

class ImagePointHandler: ...
class ImageTransformHandler: ...

def new(mode: Any, size: Any, color: int = ...): ...
def frombytes(mode: Any, size: Any, data: Any, decoder_name: str = ..., *args: Any): ...
def fromstring(*args: Any, **kw: Any) -> None: ...
def frombuffer(mode: Any, size: Any, data: Any, decoder_name: str = ..., *args: Any): ...
def fromarray(obj: Any, mode: Optional[Any] = ...): ...
def fromqimage(im: Any): ...
def fromqpixmap(im: Any): ...
def open(fp: Any, mode: str = ...): ...
def alpha_composite(im1: Any, im2: Any): ...
def blend(im1: Any, im2: Any, alpha: Any): ...
def composite(image1: Any, image2: Any, mask: Any): ...
def eval(image: Any, *args: Any): ...
def merge(mode: Any, bands: Any): ...
def register_open(id: Any, factory: Any, accept: Optional[Any] = ...) -> None: ...
def register_mime(id: Any, mimetype: Any) -> None: ...
def register_save(id: Any, driver: Any) -> None: ...
def register_save_all(id: Any, driver: Any) -> None: ...
def register_extension(id: Any, extension: Any) -> None: ...
def effect_mandelbrot(size: Any, extent: Any, quality: Any): ...
def effect_noise(size: Any, sigma: Any): ...
