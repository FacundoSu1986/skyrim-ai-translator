import asyncio
import json
import logging
import re
import threading
import urllib.parse
import urllib.request
import warnings
from collections.abc import Awaitable, Callable

from src.translator import SKYRIM_GLOSSARY

logger = logging.getLogger(__name__)

# Single-warning emission tracking per process for unauthenticated GTX endpoint
_warned_unofficial_gtx = False
_warned_lock = threading.Lock()


def _emit_gtx_deprecation_warning() -> None:
    """Emits a single deprecation warning per process about unauthenticated GTX endpoint."""
    global _warned_unofficial_gtx
    if not _warned_unofficial_gtx:
        with _warned_lock:
            if not _warned_unofficial_gtx:
                _warned_unofficial_gtx = True
                msg = (
                    "El endpoint no autenticado Google Translate (GTX) está deprecado y carece de SLA "
                    "o garantías de términos de servicio. Se recomienda configurar un proveedor recomendado "
                    "(OpenAI-compatible u Ollama)."
                )
                warnings.warn(msg, UserWarning, stacklevel=2)
                logger.warning(msg)


# Sort glossary keys by length descending to match composite terms before single words
_SORTED_GLOSSARY = sorted(SKYRIM_GLOSSARY.items(), key=lambda item: len(item[0]), reverse=True)

# One combined regex per glossary term, built once: term -> placeholder
_PLACEHOLDER_RE = {
    re.compile(re.escape(eng_term), re.IGNORECASE): f"__SKY_{i}__" for i, (eng_term, _) in enumerate(_SORTED_GLOSSARY)
}
_PLACEHOLDER_TO_ESP = {f"__SKY_{i}__": esp_term for i, (_, esp_term) in enumerate(_SORTED_GLOSSARY)}
_PLACEHOLDER_TO_ORIG = {f"__SKY_{i}__": eng_term for i, (eng_term, _) in enumerate(_SORTED_GLOSSARY)}

_LANGUAGE_CODES = {
    "spanish": "es",
    "espanol": "es",
    "español": "es",
    "es": "es",
    "english": "en",
    "ingles": "en",
    "inglés": "en",
    "en": "en",
    "french": "fr",
    "frances": "fr",
    "francés": "fr",
    "fr": "fr",
    "german": "de",
    "aleman": "de",
    "alemán": "de",
    "de": "de",
    "italian": "it",
    "italiano": "it",
    "it": "it",
    "portuguese": "pt",
    "portugues": "pt",
    "portugués": "pt",
    "pt": "pt",
}


def _resolve_lang_code(target_lang: str) -> str:
    normalized = (target_lang or "").strip().lower()
    return _LANGUAGE_CODES.get(normalized, "es")


def _protect_glossary(text: str, target_lang: str = "Spanish") -> tuple[str, dict[str, str]]:
    """
    Replaces glossary terms with placeholders in a single pass.
    If target_lang is Spanish, maps placeholders to Spanish localized lore terms.
    If target_lang is non-Spanish (French, German, etc.), maps placeholders to the original lore terms
    to prevent machine translation from corrupting canonical Bethesda terms or injecting Spanish words.
    """
    replacements: dict[str, str] = {}
    is_spanish = _resolve_lang_code(target_lang) == "es"

    for pattern, placeholder in _PLACEHOLDER_RE.items():
        if pattern.search(text):
            text = pattern.sub(placeholder, text)
            replacements[placeholder] = (
                _PLACEHOLDER_TO_ESP[placeholder] if is_spanish else _PLACEHOLDER_TO_ORIG[placeholder]
            )
    return text, replacements


def _restore_glossary(text: str, replacements: dict[str, str]) -> str:
    """Restores placeholders case-insensitively to handle translated casing variations."""
    for placeholder, term in replacements.items():
        text = re.sub(re.escape(placeholder), term, text, flags=re.IGNORECASE)
    return text


def translate_free_text_sync(text: str, target_lang: str = "Spanish") -> str:
    """
    Translates text using the free Google Translate endpoint with automatic
    Skyrim glossary protection tailored to the target language. Raises on network/API failure.
    """
    if not text or not text.strip():
        return text

    _emit_gtx_deprecation_warning()

    processed_text, replacements = _protect_glossary(text, target_lang=target_lang)

    lang_code = _resolve_lang_code(target_lang)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_code}&dt=t&q={urllib.parse.quote(processed_text)}"

    req = urllib.request.Request(
        url, headers={"User-Agent": "skyrim-ai-translator/1.0 (https://github.com/FacundoSu1986/skyrim-ai-translator)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated_pieces = [piece[0] for piece in data[0] if piece and piece[0]]
            translated_result = "".join(translated_pieces)
            return _restore_glossary(translated_result, replacements).strip()
    except Exception as e:
        logger.error("Free translation failed for '%s...': %s", text[:20], e)
        raise RuntimeError(f"Fallo del traductor gratuito: {e}") from e


def create_free_translator(target_lang: str = "Spanish") -> Callable[[str, str], Awaitable[str]]:
    """Creates a callable with fixed target_lang for translate_entries."""

    async def _call(text: str, context: str) -> str:
        return await asyncio.to_thread(translate_free_text_sync, text, target_lang)

    return _call


async def free_translator_callable(text: str, context: str) -> str:
    """Async wrapper for the free neural translator with dynamic language extraction."""
    target_lang = "Spanish"
    if "Target language:" in context:
        try:
            target_lang = context.split("Target language:")[1].split(".")[0].strip()
        except Exception:
            target_lang = "Spanish"
    return await asyncio.to_thread(translate_free_text_sync, text, target_lang)
