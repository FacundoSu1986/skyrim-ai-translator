import logging
from pathlib import Path
import edge_tts
from src.models import StringEntry

logger = logging.getLogger(__name__)

async def generate_voice_file(
    entry: StringEntry,
    output_dir: str | Path,
    voice: str = "es-ES-AlvaroNeural",
    tts_class=edge_tts.Communicate
) -> bool:
    """
    Generate a voice audio file for a translated dialog entry using edge-tts.
    
    :param entry: StringEntry object containing dialog information.
    :param output_dir: Directory where the output audio file will be saved.
    :param voice: Voice model identifier for edge-tts (default: "es-ES-AlvaroNeural").
    :param tts_class: Communicate class (defaults to edge_tts.Communicate, replaceable for testing).
    :return: True if voice file was successfully generated, False otherwise.
    """
    if not entry.is_dialog or not entry.translated_text:
        return False
        
    try:
        out_path = Path(output_dir)
        if entry.voice_type:
            out_path = out_path / entry.voice_type
        out_path.mkdir(parents=True, exist_ok=True)
        file_path = out_path / f"{entry.form_id}.mp3"
        
        communicate = tts_class(entry.translated_text, voice)
        await communicate.save(str(file_path))
        return True
    except Exception as e:
        logger.error(f"Error generating voice file for entry {entry.form_id}: {e}")
        return False

