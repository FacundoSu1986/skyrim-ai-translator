import logging
from pathlib import Path

import edge_tts

from src.models import StringEntry
from src.voice_assets import VoiceAssetMetadataError, validate_path_component

logger = logging.getLogger(__name__)


def _resolve_staged_voice_path(entry: StringEntry, output_dir: Path) -> Path:
    """
    Builds the staging file path for a dialogue entry and proves it stays under output_dir.

    Every user-controlled component (voice_type, the staged filename derived from
    form_id/string_index) must satisfy the canonical validate_path_component contract;
    the final resolved path is additionally verified against the staging root.
    Fails fast with VoiceAssetMetadataError on unsafe metadata: nothing is written
    and nothing is silently sanitized.
    """
    root = output_dir.resolve()
    staged = root
    if entry.voice_type:
        validate_path_component(entry.voice_type, "voice_type")
        staged = staged / entry.voice_type

    # Internal staging name only (de-collisions multi-response records):
    # NOT the final Skyrim/FUZ asset convention. Indexed records carry
    # their string_index so two responses of the same INFO never target
    # the same file inside asyncio.gather.
    index_suffix = f"_{entry.string_index}" if entry.string_index is not None else ""
    filename = f"{entry.form_id}{index_suffix}.mp3"
    validate_path_component(filename, "filename")

    file_path = staged / filename
    resolved = file_path.resolve()
    if not resolved.is_relative_to(root):
        raise VoiceAssetMetadataError(f"Voice staging path escapes its root: {resolved} is not under {root}")
    return file_path


async def generate_voice_file(
    entry: StringEntry, output_dir: str | Path, voice: str = "es-ES-AlvaroNeural", tts_class=edge_tts.Communicate
) -> bool:
    """
    Generate a voice audio file for a translated dialog entry using edge-tts.

    :param entry: StringEntry object containing dialog information.
    :param output_dir: Directory where the output audio file will be saved.
    :param voice: Voice model identifier for edge-tts (default: "es-ES-AlvaroNeural").
    :param tts_class: Communicate class (defaults to edge_tts.Communicate, replaceable for testing).
    :return: True if voice file was successfully generated, False otherwise.
    :raises VoiceAssetMetadataError: if voice_type/form_id fail the canonical path-component contract.
    """
    if not entry.is_dialog or not entry.translated_text:
        return False

    # Path-component and containment validation fail fast BEFORE any filesystem write.
    file_path = _resolve_staged_voice_path(entry, Path(output_dir))

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = tts_class(entry.translated_text, voice)
        await communicate.save(str(file_path))
        return True
    except Exception as e:
        logger.error(f"Error generating voice file for entry {entry.form_id}: {e}")
        return False
