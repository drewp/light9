# Stubs for PIL (Python 3)
#

class Image:
    @classmethod
    def open(cls) -> Image: ...
    @classmethod
    def frombytes(cls, mode, size, data): ...
