"""Hermetic tests for the read-only toolchain probe platform guards.

Covers the two cross-platform/load-bearing entry points the spike relies on:
- ``discover_game_root`` must fail with a domain error on non-Windows hosts
  (no raw ``ModuleNotFoundError``), and
- ``get_file_version`` must refuse a null pointer or a too-short version
  block before reading it, so a corrupt resource cannot dereference memory.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.probe_toolchain import ToolchainProbeError, discover_game_root


class _FakeVersionApi:
    """Configurable stand-in for the Win32 version API surface."""

    def __init__(self, pointer: int | None, block_length: int) -> None:
        self._pointer = pointer
        self._block_length = block_length

    def GetFileVersionInfoSizeW(self, _path: str, _handle: int) -> int:
        return 64

    def GetFileVersionInfoW(self, _path: str, _rev: int, _size: int, _buffer: Any) -> int:
        return 1

    def VerQueryValueW(self, _data: Any, _sub: str, value_ref: Any, length_ref: Any) -> int:
        value_ref._obj.value = self._pointer
        length_ref._obj.value = self._block_length
        return 1


def test_get_file_version_rejects_null_or_short_version_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    """A null pointer or a <16-byte version block yields ``None`` instead of crashing."""
    from scripts import probe_toolchain as pt

    for pointer, block_length in ((None, 16), (123456, 8)):
        fake = SimpleNamespace(version=_FakeVersionApi(pointer, block_length))
        monkeypatch.setattr(ctypes, "windll", fake)
        assert pt.get_file_version(Path("SkyrimSE.exe")) is None


def test_discover_game_root_raises_domain_error_without_winreg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-Windows hosts get ``ToolchainProbeError`` instead of ``ModuleNotFoundError``."""
    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "winreg":
            raise ModuleNotFoundError("No module named 'winreg'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(ToolchainProbeError, match="winreg"):
        discover_game_root()
