# Stubs for moviepy.audio.io.readers (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any

class FFMPEG_AudioReader:
    filename: Any = ...
    nbytes: Any = ...
    fps: Any = ...
    f: Any = ...
    acodec: Any = ...
    nchannels: Any = ...
    duration: Any = ...
    infos: Any = ...
    proc: Any = ...
    nframes: Any = ...
    buffersize: Any = ...
    buffer: Any = ...
    buffer_startframe: int = ...
    def __init__(self, filename: Any, buffersize: Any, print_infos: bool = ..., fps: int = ..., nbytes: int = ..., nchannels: int = ...) -> None: ...
    pos: Any = ...
    def initialize(self, starttime: int = ...) -> None: ...
    def skip_chunk(self, chunksize: Any) -> None: ...
    def read_chunk(self, chunksize: Any): ...
    def seek(self, pos: Any) -> None: ...
    def close_proc(self) -> None: ...
    def get_frame(self, tt: Any): ...
    def buffer_around(self, framenumber: Any) -> None: ...
    def __del__(self) -> None: ...
