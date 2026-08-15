import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request
from src.translator import SKYRIM_GLOSSARY

logger = logging.getLogger(__name__)

# One combined regex per glossary term, built once: term -> placeholder
_PLACEHOLDER_RE = {
    re.compile(re.escape(eng_term), re.IGNORECASE): f"__SKY_{i}__"
    for i, eng_term in enumerate(SKYRIM_GLOSSARY)
}
_PLACEHOLDER_TO_ESP = {
    f"__SKY_{i}__": esp_term for i, esp_term in enumerate(SKYRIM_GLOSSARY.values())
}

_LANGUAGE_CODES = {
    "spanish": "es",
    "espanol": "es",
    "es": "es",
    "english": "en",
    "en": "en",
    "french": "fr",
    "fr": "fr",
    "german": "de",
    "de": "de",
    "italian": "it",
    "it": "it",
    "portuguese": "pt",
    "pt": "pt",
}


def _resolve_lang_code(target_lang: str) -> str:
    normalized = (target_lang or "").strip().lower()
    return _LANGUAGE_CODES.get(normalized, "es")


def _protect_glossary(text: str) -> tuple[str, dict[str, str]]:
    """Replaces glossary terms with placeholders in a single pass."""
    replacements: dict[str, str] = {}
    for pattern, placeholder in _PLACEHOLDER_RE.items():
        if pattern.search(text):
            text = pattern.sub(placeholder, text)
            replacements[placeholder] = _PLACEHOLDER_TO_ESP[placeholder]
    return text, replacements


def _restore_glossary(text: str, replacements: dict[str, str]) -> str:
    for placeholder, esp_term in replacements.items():
        text = text.replace(placeholder, esp_term)
    return text


def translate_free_text_sync(text: str, target_lang: str = "Spanish") -> str:
    """
    Translates text using the free Google Translate endpoint with automatic
    Skyrim glossary protection. Raises on network/API failure instead of
    returning a fake translation.
    """
    if not text or not text.strip():
        return text

    processed_text, replacements = _protect_glossary(text)

    lang_code = _resolve_lang_code(target_lang)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_code}&dt=t&q={urllib.parse.quote(processed_text)}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated_pieces = [piece[0] for piece in data[0] if piece and piece[0]]
            translated_result = "".join(translated_pieces)
            return _restore_glossary(translated_result, replacements).strip()
    except Exception as e:
        logger.error(f"Free translation failed for '{text[:20]}...': {e}")
        raise RuntimeError(f"Fallo del traductor gratuito: {e}") from e


async def free_translator_callable(text: str, context: str) -> str:
    """Async wrapper for the free neural translator."""
    return await asyncio.to_thread(translate_free_text_sync, text, "Spanish")
