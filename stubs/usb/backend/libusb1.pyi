# Stubs for usb.backend.libusb1 (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from ctypes import *
import usb.libloader as _objfinalizer
import usb.libloader
from typing import Any, Optional

LIBUSB_ERROR_IO: int
LIBUSB_ERROR_INVALID_PARAM: int
LIBUSB_ERROR_ACCESS: int
LIBUSB_ERROR_NO_DEVICE: int
LIBUSB_ERROR_NOT_FOUND: int
LIBUSB_ERROR_BUSY: int
LIBUSB_ERROR_TIMEOUT: int
LIBUSB_ERROR_OVERFLOW: int
LIBUSB_ERROR_PIPE: int
LIBUSB_ERROR_INTERRUPTED: int
LIBUSB_ERROR_NO_MEM: int
LIBUSB_ERROR_NOT_SUPPORTED: int
LIBUSB_TRANSFER_ERROR: int
LIBUSB_TRANSFER_TIMED_OUT: int
LIBUSB_TRANSFER_CANCELLED: int
LIBUSB_TRANSFER_STALL: int
LIBUSB_TRANSFER_NO_DEVICE: int
LIBUSB_TRANSFER_OVERFLOW: int

class _libusb_endpoint_descriptor(Structure): ...
class _libusb_interface_descriptor(Structure): ...
class _libusb_interface(Structure): ...
class _libusb_config_descriptor(Structure): ...
class _libusb_device_descriptor(Structure): ...
class _libusb_iso_packet_descriptor(Structure): ...
class _libusb_transfer(Structure): ...

class _Device(_objfinalizer.AutoFinalizedObject):
    devid: Any = ...
    def __init__(self, devid: Any) -> None: ...

class _WrapDescriptor:
    obj: Any = ...
    desc: Any = ...
    def __init__(self, desc: Any, obj: Optional[Any] = ...) -> None: ...
    def __getattr__(self, name: Any): ...

class _ConfigDescriptor(_objfinalizer.AutoFinalizedObject):
    desc: Any = ...
    def __init__(self, desc: Any) -> None: ...
    def __getattr__(self, name: Any): ...

class _DevIterator(_objfinalizer.AutoFinalizedObject):
    dev_list: Any = ...
    num_devs: Any = ...
    def __init__(self, ctx: Any) -> None: ...
    def __iter__(self) -> None: ...

class _DeviceHandle:
    handle: Any = ...
    devid: Any = ...
    def __init__(self, dev: Any) -> None: ...

class _IsoTransferHandler(_objfinalizer.AutoFinalizedObject):
    transfer: Any = ...
    def __init__(self, dev_handle: Any, ep: Any, buff: Any, timeout: Any) -> None: ...
    def submit(self, ctx: Optional[Any] = ...): ...

class _LibUSB(usb.backend.IBackend):
    lib: Any = ...
    ctx: Any = ...
    def __init__(self, lib: Any) -> None: ...
    def enumerate_devices(self): ...
    def get_device_descriptor(self, dev: Any): ...
    def get_configuration_descriptor(self, dev: Any, config: Any): ...
    def get_interface_descriptor(self, dev: Any, intf: Any, alt: Any, config: Any): ...
    def get_endpoint_descriptor(self, dev: Any, ep: Any, intf: Any, alt: Any, config: Any): ...
    def open_device(self, dev: Any): ...
    def close_device(self, dev_handle: Any) -> None: ...
    def set_configuration(self, dev_handle: Any, config_value: Any) -> None: ...
    def get_configuration(self, dev_handle: Any): ...
    def set_interface_altsetting(self, dev_handle: Any, intf: Any, altsetting: Any) -> None: ...
    def claim_interface(self, dev_handle: Any, intf: Any) -> None: ...
    def release_interface(self, dev_handle: Any, intf: Any) -> None: ...
    def bulk_write(self, dev_handle: Any, ep: Any, intf: Any, data: Any, timeout: Any): ...
    def bulk_read(self, dev_handle: Any, ep: Any, intf: Any, buff: Any, timeout: Any): ...
    def intr_write(self, dev_handle: Any, ep: Any, intf: Any, data: Any, timeout: Any): ...
    def intr_read(self, dev_handle: Any, ep: Any, intf: Any, buff: Any, timeout: Any): ...
    def iso_write(self, dev_handle: Any, ep: Any, intf: Any, data: Any, timeout: Any): ...
    def iso_read(self, dev_handle: Any, ep: Any, intf: Any, buff: Any, timeout: Any): ...
    def ctrl_transfer(self, dev_handle: Any, bmRequestType: Any, bRequest: Any, wValue: Any, wIndex: Any, data: Any, timeout: Any): ...
    def clear_halt(self, dev_handle: Any, ep: Any) -> None: ...
    def reset_device(self, dev_handle: Any) -> None: ...
    def is_kernel_driver_active(self, dev_handle: Any, intf: Any): ...
    def detach_kernel_driver(self, dev_handle: Any, intf: Any) -> None: ...
    def attach_kernel_driver(self, dev_handle: Any, intf: Any) -> None: ...

def get_backend(find_library: Optional[Any] = ...): ...

# Names in __all__ with no definition:
#   LIBUSB_ERROR_OTHERLIBUSB_TRANSFER_COMPLETED
#   LIBUSB_SUCESS
