"""Single instance guard."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time

_MUTEX_HANDLE = None
_MUTEX_SA = None
MUTEX_NAME = "Local\\IdlePeek_Mutex_vlx0"
WINDOW_TITLE = "IdlePeek - darkshade"
ERROR_ALREADY_EXISTS = 183

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
advapi32 = ctypes.windll.advapi32
SW_RESTORE = 9

kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wt.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wt.BOOL),
    ]


def _null_dacl():
    advapi32.InitializeSecurityDescriptor.argtypes = [ctypes.c_void_p, wt.DWORD]
    advapi32.InitializeSecurityDescriptor.restype = wt.BOOL
    advapi32.SetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p, wt.BOOL, ctypes.c_void_p, wt.BOOL]
    advapi32.SetSecurityDescriptorDacl.restype = wt.BOOL
    sd = ctypes.create_string_buffer(64)
    if not advapi32.InitializeSecurityDescriptor(sd, 1):
        return None
    if not advapi32.SetSecurityDescriptorDacl(sd, True, None, False):
        return None
    sa = _SECURITY_ATTRIBUTES()
    sa.nLength = ctypes.sizeof(sa)
    sa.lpSecurityDescriptor = ctypes.cast(sd, ctypes.c_void_p)
    sa.bInheritHandle = False
    return sa, sd


def _mutex_attr():
    global _MUTEX_SA
    if _MUTEX_SA is None:
        _MUTEX_SA = _null_dacl()
    if not _MUTEX_SA:
        return None
    return ctypes.byref(_MUTEX_SA[0])


def release_mutex() -> None:
    global _MUTEX_HANDLE
    if _MUTEX_HANDLE:
        kernel32.CloseHandle(_MUTEX_HANDLE)
        _MUTEX_HANDLE = None


def _find_window() -> int:
    hwnd = 0
    for _ in range(20):
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            return hwnd
        time.sleep(0.05)
    return 0


def claim_or_exit() -> None:
    global _MUTEX_HANDLE
    kernel32.SetLastError(0)
    _MUTEX_HANDLE = kernel32.CreateMutexW(_mutex_attr(), False, MUTEX_NAME)
    err = kernel32.GetLastError()
    if _MUTEX_HANDLE and err != ERROR_ALREADY_EXISTS:
        return
    hwnd = _find_window()
    if hwnd:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        sys.exit(0)
    if err == ERROR_ALREADY_EXISTS:
        sys.exit(0)
    _MUTEX_HANDLE = None
