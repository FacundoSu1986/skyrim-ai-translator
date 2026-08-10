import os
import edge_tts
from src.models import StringEntry

async def generate_voice_file(
    entry: StringEntry,
    output_dir: str,
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
        
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{entry.form_id}.wav")
    
    communicate = tts_class(entry.translated_text, voice)
    await communicate.save(file_path)
    return True
