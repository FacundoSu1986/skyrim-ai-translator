"""Read-only external toolchain probe for the in-game voice asset spike (PR #9).

Discovers the proprietary Creation Kit audio toolchain on the host machine,
records SHA-256 hashes and executable versions, and writes a JSON evidence
artifact consumed by ``docs/skyrim_voice_asset_spike.md`` follow-ups.

Strictly read-only: no game files are modified, no tools are executed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BETHESDA_REGISTRY_KEY = r"SOFTWARE\WOW6432Node\Bethesda Softworks\Skyrim Special Edition"
_BETHESDA_REGISTRY_VALUE = "Installed Path"

# Relative paths of every tool required by the WAV -> LIP -> XWM -> FUZ pipeline.
_TOOLCHAIN_RELATIVE_PATHS = {
    "creation_kit": "CreationKit.exe",
    "skyrim_executable": "SkyrimSE.exe",
    "lip_generator": r"Tools\LipGen\LipGenerator\LipGenerator.exe",
    "fonix_data": r"Tools\LipGen\LipGenerator\FonixData.cdf",
    "xwma_encode": r"Tools\Audio\xwmaencode.exe",
    "lip_fuzer_reference": r"Tools\LipGen\LipFuzer\LIPFuzer.exe",
}


class ToolchainProbeError(RuntimeError):
    """Raised when the game installation cannot be located."""


def discover_game_root() -> Path:
    """Locate the Skyrim Special Edition install directory via the Windows registry."""
    import winreg

    for hive in (winreg.HKEY_LOCAL_MACHINE,):
        try:
            with winreg.OpenKey(hive, _BETHESDA_REGISTRY_KEY) as key:
                installed_path, _ = winreg.QueryValueEx(key, _BETHESDA_REGISTRY_VALUE)
        except OSError:
            continue
        root = Path(installed_path)
        if root.is_dir():
            return root
    raise ToolchainProbeError(
        "No se pudo localizar la instalación de Skyrim Special Edition en el registro de Windows"
    )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 hex digest of a file, streamed to bound memory usage."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def get_file_version(path: Path) -> str | None:
    """Read the FileVersion string of a PE executable via the Win32 version API."""
    import ctypes

    size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)  # type: ignore[attr-defined]
    if not size:
        return None
    data = ctypes.create_string_buffer(size)
    if not ctypes.windll.version.GetFileVersionInfoW(str(path), 0, size, data):  # type: ignore[attr-defined]
        return None
    value = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not ctypes.windll.version.VerQueryValueW(  # type: ignore[attr-defined]
        data, "\\", ctypes.byref(value), ctypes.byref(length)
    ):
        return None
    # VS_FIXEDFILEINFO layout: dwSignature(4), dwStrucVersion(4),
    # dwFileVersionMS(4), dwFileVersionLS(4).
    raw = ctypes.string_at(value.value, 16)
    if int.from_bytes(raw[0:4], "little") != 0xFEEF04BD:
        return None
    file_version_ms = int.from_bytes(raw[8:12], "little")
    file_version_ls = int.from_bytes(raw[12:16], "little")
    return (
        f"{file_version_ms >> 16}.{file_version_ms & 0xFFFF}."
        f"{file_version_ls >> 16}.{file_version_ls & 0xFFFF}"
    )


def probe_toolchain(game_root: Path | None = None) -> dict[str, Any]:
    """Probe every pipeline dependency and return a JSON-serializable evidence dict."""
    root = game_root if game_root is not None else discover_game_root()
    tools: dict[str, Any] = {}
    missing: list[str] = []

    for name, relative in _TOOLCHAIN_RELATIVE_PATHS.items():
        path = root / relative
        if not path.is_file():
            missing.append(name)
            tools[name] = {"path": str(path), "present": False}
            continue
        entry: dict[str, Any] = {
            "path": str(path),
            "present": True,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if path.suffix.lower() == ".exe":
            entry["file_version"] = get_file_version(path)
        tools[name] = entry

    return {
        "game_root": str(root),
        "tools": tools,
        "missing": missing,
        "pipeline_ready": not missing,
    }


def main() -> int:
    """CLI entry point: write the probe evidence JSON next to the spike documentation."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = probe_toolchain()
    out_path = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "pr9" / "toolchain_probe.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Evidence written to %s", out_path)
    if not report["pipeline_ready"]:
        logger.warning("Missing toolchain components: %s", ", ".join(report["missing"]))
        return 1
    logger.info("Full toolchain present under %s", report["game_root"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
