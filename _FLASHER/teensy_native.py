#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teensy_native — pure-Python Teensy 4.1 flasher (Windows, no external tools).

Independent Python reimplementation of the (functional) HalfKay bootloader
programming protocol, as documented by Paul Stoffregen's teensy_loader_cli:
HID device VID 0x16C0 / PID 0x0478, block size 1024, write size 1088 (3 address
bytes + 61 zero pad + 1024 data), report id 0. Intel-HEX parsing applies the
Teensy 4.x 0x60000000 FlexSPI offset. No teensy_loader_cli code is copied.

The Teensy must be in bootloader (HalfKay) mode: either press the PROGRAM
button, or pass a reboot helper (teensy_reboot.exe) to enter it automatically.
"""
import os
import sys
import time

IS_WIN = sys.platform.startswith("win")

T41_CODE_SIZE  = 8126464          # TEENSY41 code_size (teensy_loader_cli MCUs[])
T41_BLOCK_SIZE = 1024
T41_WRITE_SIZE = T41_BLOCK_SIZE + 64   # 1088
HALFKAY_VID    = 0x16C0
HALFKAY_PID    = 0x0478
HEX_MAX        = 0x1000000        # 16 MB image cap (MAX_MEMORY_SIZE)


def parse_intel_hex(path):
    """Return (image, mask, byte_count). image[i] defaults 0xFF; mask[i]=1 where set."""
    image = bytearray(b"\xff" * HEX_MAX)
    mask = bytearray(HEX_MAX)
    ext = 0
    count = 0
    with open(path, "r") as fp:
        for raw in fp:
            line = raw.strip()
            if len(line) < 11 or line[0] != ":":
                continue
            ln = int(line[1:3], 16)
            addr = int(line[3:7], 16)
            code = int(line[7:9], 16)
            payload = line[9:9 + ln * 2]
            if code == 1:                       # EOF
                break
            if code == 2 and ln == 2:           # extended segment address
                ext = int(payload, 16) << 4
                continue
            if code == 4 and ln == 2:           # extended linear address
                ext = int(payload, 16) << 16
                if 0x60000000 <= ext < 0x60000000 + T41_CODE_SIZE:
                    ext -= 0x60000000           # Teensy 4.x FlexSPI offset
                continue
            if code != 0:
                continue
            base = addr + ext
            for i in range(ln):
                p = base + i
                if 0 <= p < HEX_MAX:
                    image[p] = int(payload[i * 2:i * 2 + 2], 16)
                    mask[p] = 1
            count += ln
    return image, mask, count


# --------------------------------------------------------------------------
# Windows HID access (ctypes) — talks to the HalfKay bootloader
# --------------------------------------------------------------------------
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _setup = ctypes.WinDLL("setupapi")
    _hid = ctypes.WinDLL("hid")
    _k32 = ctypes.WinDLL("kernel32")

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                    ("Flags", wintypes.DWORD), ("Reserved", ctypes.c_void_p)]

    class HIDD_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT),
                    ("ProductID", wintypes.USHORT), ("VersionNumber", wintypes.USHORT)]

    _hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
    _hid.HidD_GetHidGuid.restype = None
    _hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
    _hid.HidD_GetAttributes.restype = wintypes.BOOLEAN
    _setup.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR,
                                            wintypes.HWND, wintypes.DWORD]
    _setup.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    _setup.SetupDiEnumDeviceInterfaces.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
        ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
    _setup.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
    _setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [wintypes.HANDLE,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _setup.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
    _setup.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
    _setup.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _k32.WriteFile.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL

    INVALID_HANDLE = ctypes.c_void_p(-1).value
    _DIGCF_PRESENT = 0x02
    _DIGCF_DEVICEINTERFACE = 0x10
    _GENERIC_RW = 0x80000000 | 0x40000000
    _FILE_SHARE_RW = 0x01 | 0x02
    _OPEN_EXISTING = 3

    def _open_path(path):
        h = _k32.CreateFileW(path, _GENERIC_RW, _FILE_SHARE_RW, None, _OPEN_EXISTING, 0, None)
        if not h or h == INVALID_HANDLE:
            return None
        return h

    def find_halfkay():
        """Return the HID device path of a HalfKay bootloader, or None."""
        guid = GUID()
        _hid.HidD_GetHidGuid(ctypes.byref(guid))
        info = _setup.SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                           _DIGCF_PRESENT | _DIGCF_DEVICEINTERFACE)
        if not info or info == INVALID_HANDLE:
            return None
        cb = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        try:
            idx = 0
            while True:
                iface = SP_DEVICE_INTERFACE_DATA()
                iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
                if not _setup.SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid),
                                                          idx, ctypes.byref(iface)):
                    break
                idx += 1
                req = wintypes.DWORD(0)
                _setup.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(iface), None, 0,
                                                        ctypes.byref(req), None)
                if req.value == 0:
                    continue
                detail = ctypes.create_string_buffer(req.value)
                ctypes.memmove(detail, ctypes.byref(wintypes.DWORD(cb)), 4)
                if not _setup.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(iface),
                                                               detail, req.value, None, None):
                    continue
                path = ctypes.wstring_at(ctypes.addressof(detail) + 4)
                h = _open_path(path)
                if not h:
                    continue
                attrib = HIDD_ATTRIBUTES()
                attrib.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
                ok = _hid.HidD_GetAttributes(h, ctypes.byref(attrib))
                _k32.CloseHandle(h)
                if ok and attrib.VendorID == HALFKAY_VID and attrib.ProductID == HALFKAY_PID:
                    return path
            return None
        finally:
            _setup.SetupDiDestroyDeviceInfoList(info)

    def _write_report(h, payload, timeout_s=0.5):
        """Write one 1088-byte HalfKay report (report id 0 -> 1089 bytes), retrying
        until the device accepts it or the timeout elapses. HalfKay briefly NAKs
        while it programs the previous block, so a single WriteFile can fail —
        teensy_loader_cli retries the same way."""
        report = b"\x00" + bytes(payload)
        cbuf = (ctypes.c_ubyte * len(report)).from_buffer_copy(report)
        written = wintypes.DWORD(0)
        deadline = time.time() + timeout_s
        while True:
            written.value = 0
            ok = _k32.WriteFile(h, cbuf, len(report), ctypes.byref(written), None)
            if ok and written.value == len(report):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(0.01)

    def _close(h):
        _k32.CloseHandle(h)
else:  # non-Windows stubs (native loader is Windows-only)
    def find_halfkay():
        return None

    def _open_path(path):
        return None

    def _write_report(h, payload, timeout_s=0.5):
        return False

    def _close(h):
        pass


def _reboot_to_bootloader(reboot_tool):
    if not reboot_tool or not os.path.isfile(reboot_tool):
        return
    try:
        import subprocess
        si = None
        flags = 0
        if IS_WIN:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            flags = 0x08000000
        subprocess.run([reboot_tool], timeout=15, capture_output=True,
                       startupinfo=si, creationflags=flags)
    except Exception:
        pass


def native_flash(hexpath, emit=lambda *a: None, reboot_tool=None, cancel=None, wait=60):
    """Flash a .hex onto a Teensy 4.1 via the HalfKay HID bootloader.
    Returns (True, message) or (False, message)."""
    if not IS_WIN:
        return False, "Il loader integrato è disponibile solo su Windows."
    image, mask, nbytes = parse_intel_hex(hexpath)
    if nbytes <= 0:
        return False, "File HEX vuoto o non valido."
    emit("firmware: %d byte (%.1f%% del flash)" % (nbytes, nbytes / T41_CODE_SIZE * 100))

    if find_halfkay() is None:
        if reboot_tool:
            emit("reboot automatico nel bootloader…")
            _reboot_to_bootloader(reboot_tool)
        emit("attendo il bootloader HalfKay…  (se non parte, premi il pulsante PROGRAM)")
        t0 = time.time()
        while find_halfkay() is None:
            if cancel and cancel():
                return False, "Operazione annullata."
            if time.time() - t0 > wait:
                return False, "Bootloader non rilevato. Premi il pulsante PROGRAM e riprova."
            time.sleep(0.25)

    path = find_halfkay()
    h = _open_path(path)
    if not h:
        return False, "Impossibile aprire il bootloader (driver HID?)."
    emit("bootloader trovato — scrittura del firmware…")
    try:
        blank = b"\xff" * T41_BLOCK_SIZE
        block_count = 0
        for addr in range(0, T41_CODE_SIZE, T41_BLOCK_SIZE):
            if block_count > 0 and 1 not in mask[addr:addr + T41_BLOCK_SIZE]:
                continue
            data = bytes(image[addr:addr + T41_BLOCK_SIZE])
            if len(data) < T41_BLOCK_SIZE:
                data += b"\xff" * (T41_BLOCK_SIZE - len(data))
            if block_count > 0 and data == blank:
                continue
            header = bytes((addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF)) + b"\x00" * 61
            timeout = 45.0 if block_count <= 4 else 0.5   # first writes wait for chip erase
            if not _write_report(h, header + data, timeout):
                return False, "Errore di scrittura al blocco 0x%06X." % addr
            block_count += 1
            if block_count % 50 == 0:
                emit("  %d blocchi scritti…" % block_count)
        _write_report(h, b"\xff\xff\xff" + b"\x00" * (T41_WRITE_SIZE - 3), 0.5)  # boot
        emit("scritti %d blocchi — riavvio." % block_count)
        return True, "Firmware scritto (%d blocchi) e Teensy riavviato." % block_count
    finally:
        _close(h)


if __name__ == "__main__":
    hexp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "ichosynth.hex")
    rb = sys.argv[2] if len(sys.argv) > 2 else None
    print("HEX:", hexp)
    print("HalfKay presente all'avvio:", find_halfkay() is not None)
    ok, msg = native_flash(hexp, emit=lambda m: print("  [native]", m), reboot_tool=rb)
    print("RISULTATO:", ok, msg)
    sys.exit(0 if ok else 1)
