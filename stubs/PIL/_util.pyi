# Stubs for PIL._util (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any

def isStringType(t: Any): ...
def isPath(f: Any): ...
def isDirectory(f: Any): ...

class deferred_error:
    ex: Any = ...
    def __init__(self, ex: Any) -> None: ...
    def __getattr__(self, elt: Any) -> None: ...
