# Stubs for cyclone.httpclient (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred
from typing import Any, Callable, Dict, List, Optional

ListType = list
DictType = dict
agent: Any
proxy_agent: Any

class StringProducer:
    body: Any = ...
    length: Any = ...
    def __init__(self, body: Any) -> None: ...
    def startProducing(self, consumer: Any): ...
    def pauseProducing(self) -> None: ...
    def stopProducing(self) -> None: ...

class Receiver(Protocol):
    finished: Any = ...
    data: Any = ...
    def __init__(self, finished: Any) -> None: ...
    def dataReceived(self, bytes: Any) -> None: ...
    def connectionLost(self, reason: Any) -> None: ...

class HTTPClient:
    url: Any = ...
    followRedirect: Any = ...
    maxRedirects: Any = ...
    headers: Any = ...
    body: Any = ...
    proxyConfig: Any = ...
    timeout: Any = ...
    agent: Any = ...
    method: Any = ...
    response: Any = ...
    body_producer: Any = ...
    def __init__(self, url: Any, *args: Any, **kwargs: Any) -> None: ...
    def fetch(self) -> None: ...

class FetchResponse:
    code: int
    phrase: bytes
    headers: Dict[bytes, List[bytes]]
    length: int
    body: bytes

def fetch(
        url: bytes,
        method: bytes=b'GET',
        followRedirect: bool = False,
        maxRedirects: int = 3,
        postdata: Optional[bytes]=None,
        headers: Optional[Dict[bytes, List[bytes]]]=None) -> Deferred[FetchResponse]: ...

class JsonRPC:
    def __init__(self, url: Any, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, attr: Any): ...
