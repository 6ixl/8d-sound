"""Звук отдельных приложений: список играющих программ и выбор их устройства вывода.

Использует тот же скрытый API Windows (AudioPolicyConfig), что и «Параметры → Звук →
Громкость приложений» и EarTrumpet. Работает на Windows 10 21H2+ и Windows 11.
"""
import ctypes
import os
from ctypes import POINTER, byref, c_uint, c_void_p, c_wchar_p, HRESULT, WINFUNCTYPE

import comtypes
from pycaw.pycaw import AudioUtilities

_combase = ctypes.windll.combase
_combase.WindowsCreateString.argtypes = [c_wchar_p, c_uint, POINTER(c_void_p)]
_combase.WindowsDeleteString.argtypes = [c_void_p]
_combase.RoGetActivationFactory.argtypes = [c_void_p, POINTER(comtypes.GUID), POINTER(c_void_p)]

IID_FACTORY = comtypes.GUID("{ab3d4648-e242-459f-b02f-541c70306324}")
IID_FACTORY_OLD = comtypes.GUID("{2a59116d-6c4f-45e0-a74f-707e3fef9258}")
MMDEV_PREFIX = "\\\\?\\SWD#MMDEVAPI#"
RENDER_SUFFIX = "#{e6327cad-dcec-4949-ae8a-991e976a79d2}"
_SET_INDEX = 25  # IInspectable(6) + 19 методов до SetPersistedDefaultAudioEndpoint

_factory = None


def _hstring(text):
    h = c_void_p()
    if text:
        _combase.WindowsCreateString(text, len(text), byref(h))
    return h


def _get_factory():
    global _factory
    if _factory is None:
        comtypes.CoInitialize()
        try:
            ctypes.windll.combase.RoInitialize(1)
        except OSError:
            pass
        name = _hstring("Windows.Media.Internal.AudioPolicyConfig")
        for iid in (IID_FACTORY, IID_FACTORY_OLD):
            ptr = c_void_p()
            hr = _combase.RoGetActivationFactory(name, byref(iid), byref(ptr))
            if hr == 0 and ptr.value:
                _factory = ptr
                break
        _combase.WindowsDeleteString(name)
        if _factory is None:
            raise OSError("Эта версия Windows не поддерживает выбор устройства для отдельных программ")
    return _factory


def _set_persisted(pid, device_id):
    fac = _get_factory()
    vtbl = ctypes.cast(fac, POINTER(POINTER(c_void_p))).contents
    proto = WINFUNCTYPE(HRESULT, c_void_p, c_uint, c_uint, c_uint, c_void_p)
    fn = proto(vtbl[_SET_INDEX])
    h = _hstring(f"{MMDEV_PREFIX}{device_id}{RENDER_SUFFIX}" if device_id else "")
    try:
        for role in (0, 1):  # eConsole, eMultimedia
            fn(fac, pid, 0, role, h)  # flow = eRender
    finally:
        if h.value:
            _combase.WindowsDeleteString(h)


def sessions():
    """{exe: [pid, ...]} программ, у которых есть звуковые сессии."""
    comtypes.CoInitialize()
    apps = {}
    for s in AudioUtilities.GetAllSessions():
        if s.Process is None:
            continue
        try:
            name = s.Process.name()
        except Exception:  # noqa: BLE001
            continue
        if name.lower() in ("8dsound.exe",):
            continue
        apps.setdefault(name, set()).add(s.ProcessId)
    return {k: sorted(v) for k, v in sorted(apps.items(), key=lambda kv: kv[0].lower())}


def _pids_of(exe):
    import psutil
    out = []
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() == exe.lower():
            out.append(p.pid)
    return out


def route_apps(exes, device_id):
    """Направить все процессы этих программ на device_id (None — вернуть по умолчанию)."""
    done = []
    for exe in exes:
        for pid in _pids_of(exe):
            try:
                _set_persisted(pid, device_id)
                done.append(exe)
            except OSError:
                pass
    return sorted(set(done))


def pretty(exe):
    return os.path.splitext(exe)[0]
