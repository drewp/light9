# Stubs for scales.samplestats (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .clock import getClock
from typing import Any

class Sampler:
    min: Any = ...
    max: Any = ...
    def __init__(self) -> None: ...
    def __len__(self): ...
    def samples(self): ...
    def update(self, value: Any) -> None: ...
    @property
    def mean(self): ...
    @property
    def stddev(self): ...
    def percentiles(self, percentiles: Any): ...

class ExponentiallyDecayingReservoir(Sampler):
    DEFAULT_SIZE: int = ...
    DEFAULT_ALPHA: float = ...
    DEFAULT_RESCALE_THRESHOLD: int = ...
    values: Any = ...
    alpha: Any = ...
    size: Any = ...
    clock: Any = ...
    rescale_threshold: Any = ...
    count: int = ...
    startTime: Any = ...
    nextScaleTime: Any = ...
    def __init__(self, size: Any = ..., alpha: Any = ..., rescale_threshold: Any = ..., clock: Any = ...) -> None: ...
    def __len__(self): ...
    def clear(self) -> None: ...
    def update(self, value: Any) -> None: ...
    def samples(self): ...

class UniformSample(Sampler):
    sample: Any = ...
    count: int = ...
    def __init__(self) -> None: ...
    def clear(self) -> None: ...
    def __len__(self): ...
    def update(self, value: Any) -> None: ...
    def __iter__(self): ...
    def samples(self): ...
