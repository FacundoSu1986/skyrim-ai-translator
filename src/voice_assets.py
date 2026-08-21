"""
Deterministic Skyrim Creation Engine Voice Asset Pipeline Module.

Pure logic only:
- Voice filename and relative path generation per Creation Kit specification.
- Fail-fast metadata and path-traversal safety validation.
- Clean-room binary FUZ container packing (FUZE magic + version 1 + LIP + XWM).
"""

import struct
from pathlib import Path
from typing import Optional
from src.models import StringEntry


class VoiceAssetMetadataError(ValueError):
    """Raised when required dialogue metadata is missing, unresolved, or invalid."""


_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "COM¹", "COM²", "COM³",
    "LPT¹", "LPT²", "LPT³",
}
_WINDOWS_FORBIDDEN_CHARS = set('<>:"/\\|?*')


_WINDOWS_MAX_COMPONENT_UNITS = 255


def _windows_utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _validate_path_component(comp: str, field_name: str) -> None:
    """
    Ensures a directory or filename path component does not contain path traversal,
    separators, null bytes, ASCII control characters, forbidden Windows characters,
    trailing periods/spaces, or reserved Windows device names.
    """
    if comp is None or not isinstance(comp, str):
        raise VoiceAssetMetadataError(f"{field_name} must be a string, got {type(comp).__name__}")

    if not comp:
        raise VoiceAssetMetadataError(f"{field_name} cannot be empty")

    if comp.startswith(" ") or comp.endswith(" "):
        raise VoiceAssetMetadataError(f"{field_name} cannot have leading or trailing whitespace: {comp!r}")

    if comp.endswith("."):
        raise VoiceAssetMetadataError(f"{field_name} cannot have trailing period: {comp!r}")

    for c in comp:
        code = ord(c)
        if code < 32:
            raise VoiceAssetMetadataError(
                f"{field_name} contains forbidden ASCII control character ({code}): {comp!r}"
            )
        if c in _WINDOWS_FORBIDDEN_CHARS:
            raise VoiceAssetMetadataError(
                f"{field_name} contains forbidden Windows character '{c}': {comp!r}"
            )

    if comp in {".", ".."}:
        raise VoiceAssetMetadataError(
            f"{field_name} contains relative directory traversal '..': {comp!r}"
        )

    try:
        component_units = _windows_utf16_units(comp)
    except UnicodeEncodeError as exc:
        raise VoiceAssetMetadataError(
            f"{field_name} contains invalid Unicode surrogate data"
        ) from exc

    if component_units > _WINDOWS_MAX_COMPONENT_UNITS:
        raise VoiceAssetMetadataError(f"{field_name} exceeds Windows component length limit")

    stem = comp.split(".")[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        raise VoiceAssetMetadataError(
            f"{field_name} uses reserved Windows device name: {comp!r}"
        )


def build_voice_basename(
    quest_edid: str,
    topic_edid: str,
    local_object_id: int,
    response_number: int,
) -> str:
    """
    Builds the deterministic voice filename basename according to Skyrim Creation Kit algorithm:
      <QuestEDID_truncated>_<TopicEDID_truncated>_<local_INFO_fid8>_<raw_TRDT_response>

    Truncation Rule:
      qlen = len(quest_edid)
      dlen = len(topic_edid)
      if qlen + dlen > 25:
          if qlen > 10:
              qlen = 10
              dlen = 15
          else:
              dlen = 25 - qlen

    FormID:
      f"{local_object_id & 0xFFFFFF:08X}"
    """
    if quest_edid is None or not isinstance(quest_edid, str):
        raise VoiceAssetMetadataError(f"quest_edid must be a string, got {type(quest_edid).__name__}")
    if topic_edid is None or not isinstance(topic_edid, str):
        raise VoiceAssetMetadataError(f"topic_edid must be a string (or empty string ''), got {type(topic_edid).__name__}")

    if not isinstance(local_object_id, int) or local_object_id < 0 or local_object_id > 0xFFFFFF:
        raise VoiceAssetMetadataError(
            f"local_object_id must be a 24-bit unsigned integer (0..0xFFFFFF), got {local_object_id}"
        )
    fid8 = f"{local_object_id & 0xFFFFFF:08X}"

    if not isinstance(response_number, int) or response_number < 0 or response_number > 255:
        raise VoiceAssetMetadataError(
            f"response_number must be an 8-bit unsigned integer (0..255), got {response_number}"
        )

    q = quest_edid
    d = topic_edid

    if len(q) + len(d) > 25:
        if len(q) > 10:
            q = q[:10]
            d = d[:15]
        else:
            d = d[:25 - len(q)]

    basename = f"{q}_{d}_{fid8}_{response_number}"
    _validate_path_component(basename, "basename")
    return basename


def build_voice_relative_path(
    defining_plugin: str,
    voice_type: str,
    basename: str,
    extension: str = ".fuz",
) -> Path:
    """
    Builds the relative Skyrim voice asset path:
      Sound/Voice/<defining_plugin>/<voice_type>/<basename><extension>
    """
    _validate_path_component(defining_plugin, "defining_plugin")
    _validate_path_component(voice_type, "voice_type")
    _validate_path_component(basename, "basename")

    if (
        not extension
        or not isinstance(extension, str)
        or not extension.startswith(".")
        or extension.startswith("..")
        or not extension[1:].isalnum()
    ):
        raise VoiceAssetMetadataError(f"invalid extension: {extension!r}")

    filename = f"{basename}{extension}"
    _validate_path_component(filename, "filename")

    return Path("Sound") / "Voice" / defining_plugin / voice_type / filename


def validate_voice_asset_entry(entry: StringEntry) -> None:
    """
    Validates that a StringEntry has all required metadata to construct a valid voice asset.
    Fails fast if any identity field is None or invalid.
    """
    if not entry.is_dialog:
        raise VoiceAssetMetadataError(f"StringEntry FormID {entry.form_id} is not a dialogue entry (is_dialog=False)")

    if not entry.defining_plugin:
        raise VoiceAssetMetadataError(f"StringEntry FormID {entry.form_id} is missing defining_plugin")
    _validate_path_component(entry.defining_plugin, "defining_plugin")

    if not entry.voice_type:
        raise VoiceAssetMetadataError(f"StringEntry FormID {entry.form_id} is missing voice_type")
    _validate_path_component(entry.voice_type, "voice_type")

    if entry.local_object_id is None:
        raise VoiceAssetMetadataError(f"StringEntry FormID {entry.form_id} is missing local_object_id")

    if entry.string_index is None:
        raise VoiceAssetMetadataError(f"StringEntry FormID {entry.form_id} is missing string_index (TRDT response number)")

    if entry.quest_edid is None:
        raise VoiceAssetMetadataError(f"StringEntry FormID {entry.form_id} has unresolved quest_edid (None)")

    if entry.topic_edid is None:
        raise VoiceAssetMetadataError(f"StringEntry FormID {entry.form_id} has unresolved topic_edid (None)")


def pack_fuz(lip_bytes: bytes, xwm_bytes: bytes) -> bytes:
    """
    Packs raw LIP phonetic stream and XWM audio stream into a standard Skyrim FUZ container.

    Binary Format:
      - 4 bytes ASCII magic: b"FUZE" (0x46555A45)
      - uint32 LE version: 1
      - uint32 LE lip_size: byte length of the LIP stream
      - lip_bytes
      - xwm_bytes
    """
    if not isinstance(lip_bytes, (bytes, bytearray)) or len(lip_bytes) == 0:
        raise VoiceAssetMetadataError("lip_bytes must be non-empty bytes")
    if not isinstance(xwm_bytes, (bytes, bytearray)) or len(xwm_bytes) == 0:
        raise VoiceAssetMetadataError("xwm_bytes must be non-empty bytes")

    lip_len = len(lip_bytes)
    header = b"FUZE" + struct.pack("<II", 1, lip_len)
    return header + bytes(lip_bytes) + bytes(xwm_bytes)


def unpack_fuz(fuz_bytes: bytes) -> tuple[bytes, bytes]:
    """
    Unpacks a Skyrim FUZ container into its constituent LIP and audio byte streams.
    Returns (lip_bytes, audio_bytes).
    """
    if not isinstance(fuz_bytes, (bytes, bytearray)) or len(fuz_bytes) < 12:
        raise VoiceAssetMetadataError(f"fuz_bytes too short for valid FUZE header (got {len(fuz_bytes)} bytes)")

    magic = fuz_bytes[:4]
    if magic != b"FUZE":
        raise VoiceAssetMetadataError(f"Invalid FUZ magic header: {magic!r}, expected b'FUZE'")

    version, lip_size = struct.unpack("<II", fuz_bytes[4:12])
    if version != 1:
        raise VoiceAssetMetadataError(f"Unsupported FUZ container version {version}, expected 1")

    total_len = len(fuz_bytes)
    if total_len < 12 + lip_size:
        raise VoiceAssetMetadataError(
            f"Truncated FUZ payload: declared LIP size {lip_size} bytes, total buffer {total_len} bytes"
        )

    lip_payload = bytes(fuz_bytes[12:12+lip_size])
    audio_payload = bytes(fuz_bytes[12+lip_size:])

    if len(lip_payload) == 0:
        raise VoiceAssetMetadataError("FUZ container contains zero-length LIP stream")
    if len(audio_payload) == 0:
        raise VoiceAssetMetadataError("FUZ container contains zero-length audio stream")

    return lip_payload, audio_payload
