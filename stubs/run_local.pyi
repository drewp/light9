# Stubs for run_local (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import logging
from typing import Any

def fixSysPath() -> None: ...
def rce(self, exc: Any, val: Any, tb: Any) -> None: ...

progName: Any
log: Any

class FractionTimeFilter(logging.Filter):
    def filter(self, record: Any): ...

def setTerminalTitle(s: Any) -> None: ...
