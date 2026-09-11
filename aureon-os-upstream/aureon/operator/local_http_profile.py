"""Windows-user-protected credentials for the private local HTTP pair.

Only the operator and its loopback UI proxy receive this credential. This
profile changes HTTP authentication, not protected-action release authority.
No secret is written in plaintext or returned by the command-line interface.
"""
from __future__ import annotations

import ctypes
import json
import os
import secrets
from pathlib import Path

PROFILE_PATH = Path.home() / ".aureon" / "operator-http.dpapi"
_SERVICES = frozenset({"operator_gateway", "frontend_vite"})


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("local_http_profile_requires_windows_dpapi")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, destination = Blob(len(data), buffer), Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    name = "CryptUnprotectData" if decrypt else "CryptProtectData"
    fn = getattr(crypt, name)
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    # UI_FORBIDDEN, without LOCAL_MACHINE: scoped to this Windows account.
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(destination)):
        raise RuntimeError("local_http_profile_dpapi_failed")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel.LocalFree(destination.pbData)


def _read(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) > 16384:
        raise ValueError("local_http_profile_too_large")
    profile = json.loads(_dpapi(raw, decrypt=True))
    bearer = profile.get("operator_bearer") if isinstance(profile, dict) else None
    if (not isinstance(profile, dict) or profile.get("schema") != "aureon.local-http-profile.v1"
            or not isinstance(bearer, str) or len(bearer) < 48
            or len(bearer) > 128 or not all(c.isalnum() or c in "_-" for c in bearer)):
        raise ValueError("local_http_profile_invalid")
    return profile


def initialize(path: Path = PROFILE_PATH) -> None:
    if path.exists():
        _read(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = _dpapi(json.dumps({"schema": "aureon.local-http-profile.v1",
                                  "operator_bearer": secrets.token_urlsafe(48)}).encode(), decrypt=False)
    try:
        with path.open("xb") as handle:
            handle.write(encrypted)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        _read(path)


def service_environment(service: str, environment: dict[str, str], *, path: Path = PROFILE_PATH, required: bool = False) -> dict[str, str]:
    """Apply an installed profile only to its two named services; no side effects."""
    result = dict(environment)
    if service not in _SERVICES:
        return result
    if not path.exists():
        if required:
            raise RuntimeError("commissioned_local_http_profile_missing")
        return result
    profile = _read(path)
    if service == "operator_gateway":
        result.update({"AUREON_OPERATOR_API_KEY": profile["operator_bearer"],
                       "AUREON_OPERATOR_ENV": "production", "AUREON_OPERATOR_DEV": "0",
                       "AUREON_OPERATOR_HOST": "127.0.0.1", "AUREON_OPERATOR_PORT": "8080",
                       "AUREON_OPERATOR_RATE_RPS": "40", "AUREON_OPERATOR_RATE_BURST": "160",
                       "AUREON_OPERATOR_HTTP_PROCESSES": "1", "AUREON_OPERATOR_REPLICAS": "1"})
    else:
        result.update({"AUREON_UI_AUTH_MODE": "local-operator",
                       "AUREON_OPERATOR_PROXY_BEARER": profile["operator_bearer"],
                       # This service is Vite's development server. A production
                       # React dependency exports jsxDEV as undefined, while
                       # SWC serves development JSX, leaving a blank root.
                       "NODE_ENV": "development"})
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    if args.initialize:
        initialize()
    _read(PROFILE_PATH)
    print(json.dumps({"available": True, "storage": "windows_current_user_dpapi",
                      "scope": "private_local_http", "release_authority": False}))
