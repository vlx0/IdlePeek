"""Last input age and the active scheme's sleep timeouts."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass

powrprof = ctypes.windll.powrprof
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

SUB_SLEEP = "238c9fa8-0aad-41ed-83f4-97be242c8f20"
SUB_VIDEO = "7516b95f-f776-4464-8c53-06167f40cc99"
STANDBY_IDLE = "29f6c1db-86da-48c5-9fdb-f2b67b1f44da"
HIBERNATE_IDLE = "9d7815a6-7ee4-497e-8888-515a05f02364"
AWAY_MODE = "25dfa149-5dd1-4736-b5ab-e8a37b5b8187"
VIDEO_IDLE = "3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e"


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wt.BYTE),
        ("BatteryFlag", wt.BYTE),
        ("BatteryLifePercent", wt.BYTE),
        ("SystemStatusFlag", wt.BYTE),
        ("BatteryLifeTime", wt.DWORD),
        ("BatteryFullLifeTime", wt.DWORD),
    ]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("dwTime", wt.DWORD),
    ]


user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetLastInputInfo.restype = wt.BOOL


@dataclass
class Snap:
    idle_sec: int = 0
    scheme: str = ""
    on_ac: bool = True
    sleep_sec: int | None = None
    display_sec: int | None = None
    hibernate_sec: int | None = None
    away: int | None = None
    error: str = ""


def format_span(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} с"
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} мин {rest} с" if rest else f"{minutes} мин"
    hours, minutes = divmod(minutes, 60)
    if minutes:
        return f"{hours} ч {minutes} мин"
    return f"{hours} ч"


def format_after(seconds: int | None) -> str:
    if seconds is None:
        return "не прочитан"
    if seconds == 0:
        return "никогда"
    return f"через {format_span(seconds)}"


def leftover(idle_sec: int, timeout_sec: int | None) -> str:
    if timeout_sec is None:
        return "не прочитан"
    if timeout_sec == 0:
        return "в схеме выключен"
    left = timeout_sec - idle_sec
    if left > 0:
        return f"ещё {format_span(left)}"
    return "уже должен был"


def overdue(idle_sec: int, timeout_sec: int | None) -> bool:
    return timeout_sec is not None and timeout_sec > 0 and idle_sec >= timeout_sec


def sample() -> Snap:
    snap = Snap()
    try:
        snap.idle_sec = _idle_sec()
    except OSError:
        snap.error = "время простоя не прочиталось."
        return snap
    try:
        snap.scheme, snap.on_ac, snap.sleep_sec, snap.display_sec, snap.hibernate_sec, snap.away = _scheme()
    except OSError:
        snap.error = "схема питания не прочиталась."
    return snap


def _idle_sec() -> int:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        raise OSError("GetLastInputInfo")
    idle_ms = (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return idle_ms // 1000


def _guid(text: str) -> GUID:
    a, b, c, d, e = text.strip("{}").lower().split("-")
    raw = bytes.fromhex(d + e)
    g = GUID()
    g.Data1 = int(a, 16)
    g.Data2 = int(b, 16)
    g.Data3 = int(c, 16)
    for i, x in enumerate(raw):
        g.Data4[i] = x
    return g


def _scheme_name(g: GUID) -> str:
    buf = ctypes.create_unicode_buffer(256)
    size = wt.DWORD(ctypes.sizeof(buf))
    if powrprof.PowerReadFriendlyName(None, ctypes.byref(g), None, None, buf, ctypes.byref(size)) == 0:
        return buf.value.strip()
    return ""


def _active_scheme() -> tuple[str, GUID | None]:
    ptr = ctypes.POINTER(GUID)()
    rc = powrprof.PowerGetActiveScheme(None, ctypes.byref(ptr))
    if rc != 0 or not ptr:
        return "", None
    try:
        gid = GUID()
        ctypes.memmove(ctypes.byref(gid), ptr, ctypes.sizeof(GUID))
        return _scheme_name(gid), gid
    finally:
        kernel32.LocalFree(ptr)


def _on_ac() -> bool:
    status = SYSTEM_POWER_STATUS()
    if not kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return True
    return status.ACLineStatus != 0


def _index(scheme: GUID | None, subgroup: str, setting: str, ac: bool) -> int | None:
    if scheme is None:
        return None
    group = _guid(subgroup)
    item = _guid(setting)
    val = wt.DWORD()
    fn = powrprof.PowerReadACValueIndex if ac else powrprof.PowerReadDCValueIndex
    rc = fn(None, ctypes.byref(scheme), ctypes.byref(group), ctypes.byref(item), ctypes.byref(val))
    if rc != 0:
        return None
    return int(val.value)


def _scheme() -> tuple[str, bool, int | None, int | None, int | None, int | None]:
    name, scheme = _active_scheme()
    ac = _on_ac()
    return (
        name,
        ac,
        _index(scheme, SUB_SLEEP, STANDBY_IDLE, ac),
        _index(scheme, SUB_VIDEO, VIDEO_IDLE, ac),
        _index(scheme, SUB_SLEEP, HIBERNATE_IDLE, ac),
        _index(scheme, SUB_SLEEP, AWAY_MODE, ac),
    )
