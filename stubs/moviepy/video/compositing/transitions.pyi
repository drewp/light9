# Stubs for moviepy.video.compositing.transitions (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from .CompositeVideoClip import CompositeVideoClip
from typing import Any

def crossfadein(clip: Any, duration: Any): ...
def crossfadeout(clip: Any, duration: Any): ...
def slide_in(clip: Any, duration: Any, side: Any): ...
def slide_out(clip: Any, duration: Any, side: Any): ...
def make_loopable(clip: Any, cross_duration: Any): ...
