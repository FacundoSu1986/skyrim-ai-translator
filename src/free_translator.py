import asyncio
import json
import logging
import urllib.parse
import urllib.request
from src.translator import SKYRIM_GLOSSARY

logger = logging.getLogger(__name__)

def translate_free_text_sync(text: str, target_lang: str = "es") -> str:
    """
    Translates text to Spanish (or target language) using free neural translation API with
    automatic Skyrim glossary consistency replacement.
    """
    if not text or not text.strip():
        return text

    # Pre-process: protect Skyrim glossary terms
    processed_text = text
    term_replacements = {}
    for eng_term, esp_term in SKYRIM_GLOSSARY.items():
        if eng_term.lower() in processed_text.lower():
            placeholder = f"__SKY_{abs(hash(eng_term)) % 10000}__"
            term_replacements[placeholder] = esp_term
            # Case-insensitive replace for glossary
            import re
            processed_text = re.sub(re.escape(eng_term), placeholder, processed_text, flags=re.IGNORECASE)

    # Call free Google Translate endpoint
    lang_code = "es" if "span" in target_lang.lower() else "es"
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_code}&dt=t&q={urllib.parse.quote(processed_text)}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated_pieces = [piece[0] for piece in data[0] if piece and piece[0]]
            translated_result = "".join(translated_pieces)

            # Restore glossary terms
            for placeholder, esp_term in term_replacements.items():
                translated_result = translated_result.replace(placeholder, esp_term)

            return translated_result.strip()
    except Exception as e:
        logger.warning(f"Free translation fallback failed for '{text[:20]}...': {e}")
        # Fallback to applying glossary on original text
        fallback = text
        for eng_term, esp_term in SKYRIM_GLOSSARY.items():
            import re
            fallback = re.sub(re.escape(eng_term), esp_term, fallback, flags=re.IGNORECASE)
        return fallback


async def free_translator_callable(text: str, context: str) -> str:
    """Async wrapper for the free neural translator."""
    return await asyncio.to_thread(translate_free_text_sync, text, "es")
