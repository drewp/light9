# Stubs for greplin.scales.util (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import threading
from typing import Any, Optional

log: Any

def lookup(source: Any, keys: Any, fallback: Optional[Any] = ...): ...

class GraphiteReporter(threading.Thread):
    sock: Any = ...
    queue: Any = ...
    maxQueueSize: Any = ...
    daemon: bool = ...
    def __init__(self, host: Any, port: Any, maxQueueSize: int = ...) -> None: ...
    def run(self) -> None: ...
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def log(self, name: Any, value: Any, valueType: Optional[Any] = ..., stamp: Optional[Any] = ...) -> None: ...
    def enqueue(self, name: Any, value: Any, valueType: Optional[Any] = ..., stamp: Optional[Any] = ...) -> None: ...
    def flush(self) -> None: ...
    def shutdown(self) -> None: ...

class AtomicValue:
    lock: Any = ...
    value: Any = ...
    def __init__(self, val: Any) -> None: ...
    def update(self, function: Any): ...
    def getAndSet(self, newVal: Any): ...
    def addAndGet(self, val: Any): ...

class EWMA:
    M1_ALPHA: Any = ...
    M5_ALPHA: Any = ...
    M15_ALPHA: Any = ...
    TICK_RATE: int = ...
    @classmethod
    def oneMinute(cls): ...
    @classmethod
    def fiveMinute(cls): ...
    @classmethod
    def fifteenMinute(cls): ...
    alpha: Any = ...
    interval: Any = ...
    rate: int = ...
    def __init__(self, alpha: Any, interval: Any) -> None: ...
    def update(self, val: Any) -> None: ...
    def tick(self) -> None: ...
