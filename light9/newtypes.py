from typing import Tuple, NewType
from rdflib import URIRef

ClientType = NewType('ClientType', str)
ClientSessionType = NewType('ClientSessionType', str)
Curve = NewType('Curve', URIRef)
OutputUri = NewType('OutputUri', URIRef)  # e.g. dmxA
DeviceUri = NewType('DeviceUri', URIRef)  # e.g. :aura2
DeviceClass = NewType('DeviceClass', URIRef)  # e.g. :Aura
DmxIndex = NewType('DmxIndex', int)  # 1..512
DmxMessageIndex = NewType('DmxMessageIndex', int)  # 0..511
DeviceAttr = NewType('DeviceAttr', URIRef)  # e.g. :rx
NoteUri = NewType('NoteUri', URIRef)
OutputAttr = NewType('OutputAttr', URIRef)  # e.g. :xFine
OutputValue = NewType('OutputValue', int)  # byte in dmx message
Song = NewType('Song', URIRef)
UnixTime = NewType('UnixTime', float)

# Alternate output range for a device. Instead of outputting 0.0 to
# 1.0, you can map that range into, say, 0.2 to 0.7
OutputRange = NewType('OutputRange', Tuple[float, float])
