from typing import Any

class IDelayedCall:
    def getTime(self) -> Any: ...
    def cancel(self) -> None: ...
    def delay(self, secondsLater: Any) -> None: ...
    def reset(self, secondsFromNow: Any) -> None: ...
    def active(self) -> None: ...


class IAddress:  # this is https://twistedmatrix.com/documents/current/api/twisted.internet.address.IPv4Address.html
    type: str
    host: str
    port: int   
    
class IListeningPort:
    def startListening(self): ...
    def stopListening(self): ... # returns deferred
    def getHost(self) -> IAddress: ...
    _realPortNumber: int # from t.i.tcp.Port
