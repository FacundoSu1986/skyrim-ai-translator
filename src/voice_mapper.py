from typing import Optional

# Mapping Skyrim VoiceType identifiers to optimal Microsoft Edge-TTS neural voices
SKYRIM_VOICE_MAP = {
    # --- FEMALE VOICES ---
    "FemaleCommander": "es-ES-ElviraNeural",
    "FemaleCommoner": "es-ES-ElviraNeural",
    "FemaleCondescending": "es-ES-ElviraNeural",
    "FemaleCoward": "es-MX-DaliaNeural",
    "FemaleDarkElf": "es-ES-ElviraNeural",
    "FemaleElfHaughty": "es-ES-ElviraNeural",
    "FemaleEvenToned": "es-ES-ElviraNeural",
    "FemaleNord": "es-ES-ElviraNeural",
    "FemaleOldGrumpy": "es-ES-ElviraNeural",
    "FemaleOldKindly": "es-ES-ElviraNeural",
    "FemaleOrc": "es-ES-ElviraNeural",
    "FemaleShrill": "es-MX-DaliaNeural",
    "FemaleSultry": "es-ES-ElviraNeural",
    "FemaleYoungEager": "es-MX-DaliaNeural",
    "FemaleChild": "es-MX-DaliaNeural",
    "FemaleKhajiit": "es-ES-ElviraNeural",
    "FemaleArgonian": "es-ES-ElviraNeural",

    # --- MALE VOICES ---
    "MaleNord": "es-ES-AlvaroNeural",
    "MaleBrute": "es-ES-AlvaroNeural",
    "MaleCommander": "es-ES-AlvaroNeural",
    "MaleCommoner": "es-ES-AlvaroNeural",
    "MaleCommonerAccented": "es-MX-JorgeNeural",
    "MaleCondescending": "es-ES-AlvaroNeural",
    "MaleCoward": "es-ES-DarioNeural",
    "MaleDarkElf": "es-ES-AlvaroNeural",
    "MaleDrunk": "es-ES-AlvaroNeural",
    "MaleElfHaughty": "es-ES-AlvaroNeural",
    "MaleEvenToned": "es-ES-AlvaroNeural",
    "MaleEvenTonedAccented": "es-MX-JorgeNeural",
    "MaleGuard": "es-ES-AlvaroNeural",
    "MaleNordCrazy": "es-ES-AlvaroNeural",
    "MaleOldGrumpy": "es-ES-AlvaroNeural",
    "MaleOldKindly": "es-ES-AlvaroNeural",
    "MaleOrc": "es-ES-AlvaroNeural",
    "MaleSly": "es-ES-DarioNeural",
    "MaleSoldier": "es-ES-AlvaroNeural",
    "MaleWarlock": "es-ES-AlvaroNeural",
    "MaleYoungEager": "es-ES-DarioNeural",
    "MaleChild": "es-ES-DarioNeural",
    "MaleKhajiit": "es-ES-AlvaroNeural",
    "MaleArgonian": "es-ES-AlvaroNeural",
}

def resolve_voice_for_entry(voice_type: Optional[str], default_fallback: str = "es-ES-AlvaroNeural") -> str:
    """
    Returns the most fitting Edge-TTS neural voice based on the Skyrim VoiceType.
    Falls back to a female voice if 'Female' is in the name, or male if 'Male', or default.
    """
    if not voice_type:
        return default_fallback

    # Direct match
    if voice_type in SKYRIM_VOICE_MAP:
        return SKYRIM_VOICE_MAP[voice_type]

    # Heuristic match
    lower = voice_type.lower()
    if "female" in lower or "woman" in lower or "girl" in lower or "fem" in lower:
        return "es-ES-ElviraNeural"
    if "child" in lower or "kid" in lower or "young" in lower:
        return "es-ES-DarioNeural"
    if "male" in lower or "man" in lower or "boy" in lower or "guard" in lower or "nord" in lower:
        return "es-ES-AlvaroNeural"

    return default_fallback
