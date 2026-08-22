"""
Camino de traduccion "gratuito", apoyado en el endpoint web de Google Translate.

AVISO LEGAL
-----------
`translate.googleapis.com/translate_a/single` es el endpoint interno que usa la
web de Google Translate, no una API publica. Google no publica contrato ni
cuota para el, y sus Terminos de Servicio prohiben acceder a los Servicios
"por un metodo distinto de la interfaz y las instrucciones que proporcionamos".
Usarlo de forma programada queda por tanto fuera de los terminos aceptados: el
endpoint puede cambiar o cortarse sin previo aviso y el uso es responsabilidad
de quien despliega la herramienta.

La alternativa conforme es Google Cloud Translation API (o DeepL, o el camino
LLM de `src/translator.py`), que requieren credencial y tienen cuota facturable.
Ver docs/legal/COMPLIANCE-REVIEW.md, hallazgo L-02.

Este modulo se identifica honestamente ante el servidor: no suplanta a un
navegador. Falsear el User-Agent agravaria el incumplimiento sin aportar nada.
"""

import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Awaitable, Callable
from src.translator import SKYRIM_GLOSSARY

logger = logging.getLogger(__name__)

# User-Agent honesto: identifica al proyecto en lugar de imitar a Chrome.
_USER_AGENT = (
    "skyrim-ai-translator/1.0 "
    "(+https://github.com/FacundoSu1986/skyrim-ai-translator)"
)

_TOS_NOTICE = (
    "El traductor gratuito usa el endpoint interno de Google Translate, que "
    "queda fuera de los Terminos de Servicio de Google para uso programado. "
    "Para un despliegue conforme, configura una API oficial (Google Cloud "
    "Translation, DeepL) o el camino LLM. Ver docs/legal/COMPLIANCE-REVIEW.md."
)

# El aviso se emite una sola vez por proceso: es informacion para el operador,
# no ruido por cada una de las miles de lineas de un mod.
_tos_notice_emitted = False


def _warn_unofficial_endpoint_once() -> None:
    global _tos_notice_emitted
    if not _tos_notice_emitted:
        _tos_notice_emitted = True
        logger.warning(_TOS_NOTICE)


# Sort glossary keys by length descending to match composite terms before single words
_SORTED_GLOSSARY = sorted(SKYRIM_GLOSSARY.items(), key=lambda item: len(item[0]), reverse=True)

# One combined regex per glossary term, built once: term -> placeholder
_PLACEHOLDER_RE = {
    re.compile(re.escape(eng_term), re.IGNORECASE): f"__SKY_{i}__"
    for i, (eng_term, _) in enumerate(_SORTED_GLOSSARY)
}
_PLACEHOLDER_TO_ESP = {
    f"__SKY_{i}__": esp_term for i, (_, esp_term) in enumerate(_SORTED_GLOSSARY)
}
_PLACEHOLDER_TO_ORIG = {
    f"__SKY_{i}__": eng_term for i, (eng_term, _) in enumerate(_SORTED_GLOSSARY)
}

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
            replacements[placeholder] = _PLACEHOLDER_TO_ESP[placeholder] if is_spanish else _PLACEHOLDER_TO_ORIG[placeholder]
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

    Uses an undocumented endpoint whose programmatic use falls outside Google's
    Terms of Service; see the module docstring before deploying this path.
    """
    if not text or not text.strip():
        return text

    _warn_unofficial_endpoint_once()

    processed_text, replacements = _protect_glossary(text, target_lang=target_lang)

    lang_code = _resolve_lang_code(target_lang)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_code}&dt=t&q={urllib.parse.quote(processed_text)}"

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
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
