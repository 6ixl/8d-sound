"""Переключение устройства вывода Windows по умолчанию (IPolicyConfig)."""
from ctypes import HRESULT, c_int, c_void_p
from ctypes.wintypes import LPCWSTR

import comtypes
from comtypes import COMMETHOD, GUID, IUnknown
from pycaw.pycaw import AudioUtilities


class IPolicyConfig(IUnknown):
    _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
    _methods_ = [COMMETHOD([], HRESULT, name, (["in"], c_void_p, "a"), (["in"], c_void_p, "b"))
                 for name in ("GetMixFormat", "GetDeviceFormat", "ResetDeviceFormat", "SetDeviceFormat",
                              "GetProcessingPeriod", "SetProcessingPeriod", "GetShareMode", "SetShareMode",
                              "GetPropertyValue", "SetPropertyValue")] + [
        COMMETHOD([], HRESULT, "SetDefaultEndpoint", (["in"], LPCWSTR, "id"), (["in"], c_int, "role")),
    ]


CLSID_POLICY = GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}")


def _render_devices():
    out = []
    for d in AudioUtilities.GetAllDevices():
        if d.id and d.id.startswith("{0.0.0.") and "Active" in str(d.state):
            out.append((d.id, d.FriendlyName or ""))
    return out


def get_default_output():
    comtypes.CoInitialize()
    enum = AudioUtilities.GetDeviceEnumerator()
    return enum.GetDefaultAudioEndpoint(0, 0).GetId()


def set_default_output(dev_id):
    comtypes.CoInitialize()
    policy = comtypes.CoCreateInstance(CLSID_POLICY, IPolicyConfig, comtypes.CLSCTX_ALL)
    for role in (0, 1, 2):
        policy.SetDefaultEndpoint(dev_id, role)


def find_output(part):
    return next((i for i, n in _render_devices() if part.lower() in n.lower()), None)
