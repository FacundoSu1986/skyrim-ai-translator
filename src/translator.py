import asyncio
import ipaddress
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import replace

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # noqa: UP042
        pass


from src.models import StringEntry

logger = logging.getLogger(__name__)


def _validate_api_base(api_base: str) -> str:
    """Valida que api_base sea una URL HTTP/HTTPS válida y no apunte a endpoints no autorizados."""
    if not isinstance(api_base, str) or not api_base.strip():
        raise ValueError("api_base no puede estar vacío")

    parsed = urllib.parse.urlsplit(api_base.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Esquema no permitido en api_base: {parsed.scheme!r}. Solo se permite http o https.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"api_base carece de host válido: {api_base!r}")

    # Bloquear explícitamente endpoints de metadatos de instancias en la nube (ej. link-local 169.254.169.254)
    hostname_clean = hostname.strip("[]")
    try:
        ip = ipaddress.ip_address(hostname_clean)
        if ip.is_link_local:
            raise ValueError(f"Destino no permitido en api_base (dirección link-local/metadatos de nube): {hostname}")
    except ValueError as e:
        if "link-local" in str(e):
            raise

    return api_base.rstrip("/")


class TranslationProvider(StrEnum):
    """
    Identificadores de proveedores de traducción soportados.

    Proveedores recomendados:
    - OPENAI_COMPATIBLE: Recomendado para traducciones productivas y alta calidad vía
      APIs remotas compatibles con OpenAI (OpenAI, DeepSeek, Groq, OpenRouter).
    - OLLAMA: Recomendado para traducción local, privada y offline ejecutada en el
      mismo host mediante modelos LLM locales (Llama 3, Mistral, Qwen).

    Proveedor deprecado / fallback:
    - UNOFFICIAL_GTX: Endpoint no autenticado de Google Translate. Deprecado, sin SLA,
      sin garantía de estabilidad y sujeto a límites no documentados de términos de servicio.
    """

    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"
    UNOFFICIAL_GTX = "unofficial_gtx"


# Official Skyrim Spanish localization glossary
SKYRIM_GLOSSARY = {
    "Dragonborn": "Sangre de Dragón",
    "Dovahkiin": "Dovahkiin",
    "Whiterun": "Carrera Blanca",
    "Solitude": "Soledad",
    "Windhelm": "Ventalia",
    "Riften": "Riften",
    "Markarth": "Markarth",
    "Falkreath": "Falkreath",
    "Dawnstar": "Lucero del Alba",
    "Morthal": "Morthal",
    "Winterhold": "Hibernalia",
    "Bleak Falls Barrow": "Túmulo de las Cataratas Lúgubres",
    "High Hrothgar": "Alto Hrothgar",
    "Greybeards": "Barbas Grises",
    "Jarl": "Jarl",
    "Thane": "Thane",
    "Huscarl": "Edecán",
    "Septim": "Septim",
    "Draugr": "Draugr",
    "Dragon Priest": "Sacerdote Dragón",
    "Alduin": "Alduin",
    "Paarthurnax": "Paarthurnax",
    "Sovngarde": "Sovngarde",
    "Stormcloaks": "Capas de la Tormenta",
    "Imperial Legion": "Legión Imperial",
    "Dark Brotherhood": "Hermandad Oscura",
    "Thieves Guild": "Gremio de Ladrones",
    "College of Winterhold": "Colegio de Hibernalia",
    "Companions": "Compañeros",
    "Nightingale": "Ruiseñor",
    "Solstheim": "Solstheim",
    "Raven Rock": "Roca del Cuervo",
    "Tel Mithryn": "Tel Mithryn",
    "Blackreach": "Límite Sombrío",
    "Soul Cairn": "Recordatorio de las Almas",
    "Skyforge": "Forja del Cielo",
    "Sweetroll": "Bollo dulce",
}


def _is_spanish(target_lang: str) -> bool:
    normalized = (target_lang or "").strip().lower()
    return normalized in {"spanish", "espanol", "español", "es"}


def build_skyrim_system_prompt(target_lang: str = "Spanish") -> str:
    """
    Builds the expert Skyrim translation system prompt dynamically.
    Includes the official Spanish lore glossary when target_lang is Spanish,
    or instructs fidelity to medieval fantasy lore without Spanish glossary pollution for other languages.
    """
    if _is_spanish(target_lang):
        glossary_items = "\n".join(f"- {eng} -> {esp}" for eng, esp in SKYRIM_GLOSSARY.items())
        glossary_clause = (
            f"1. Respeta estrictamente el lore y el siguiente glosario oficial de Skyrim:\n{glossary_items}\n"
        )
    else:
        glossary_clause = f"1. Translate accurately into {target_lang}, preserving canonical Bethesda names, locations, and titles in their standard official {target_lang} or fantasy forms.\n"

    return (
        f"Eres un traductor experto y localizador profesional para The Elder Scrolls V: Skyrim.\n"
        f"Tu objetivo es traducir textos, nombres y diálogos al idioma '{target_lang}' manteniendo el tono medieval/fantástico y la coherencia del doblaje oficial.\n"
        f"Reglas:\n"
        f"{glossary_clause}"
        f"2. Conserva caracteres especiales de formato, placeholders ({{...}}, <...>), y etiquetas de Skyrim intactos.\n"
        f"3. Devuelve únicamente la traducción limpia, sin explicaciones ni comillas adicionales."
    )


SKYRIM_SYSTEM_PROMPT = build_skyrim_system_prompt("Spanish")


async def default_llm_call(text: str, context: str) -> str:
    """Default fallback translation function."""
    return f"Translated: {text}"


def create_openai_compatible_translator(
    api_key: str,
    api_base: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    target_lang: str = "Spanish",
) -> Callable[[str, str], Awaitable[str]]:
    """Creates an async translation callable targeting any OpenAI-compatible API (OpenAI, DeepSeek, Groq, Ollama, OpenRouter)."""
    clean_api_base = _validate_api_base(api_base)

    async def _call(text: str, context: str) -> str:
        if not api_key and "localhost" not in clean_api_base and "127.0.0.1" not in clean_api_base:
            raise RuntimeError("Se requiere api_key para usar una API remota compatible con OpenAI")

        url = f"{clean_api_base}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}" if api_key else ""}

        # Extract target_lang dynamically if provided in context
        eff_target_lang = target_lang
        if "Target language:" in context:
            try:
                eff_target_lang = context.split("Target language:")[1].split(".")[0].strip()
            except Exception:
                eff_target_lang = target_lang

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": build_skyrim_system_prompt(eff_target_lang)},
                {"role": "user", "content": f"{context}\nTexto a traducir:\n{text}"},
            ],
            "temperature": 0.3,
        }

        def _request_sync():
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()

        try:
            return await asyncio.to_thread(_request_sync)
        except Exception as e:
            logger.error("Error calling LLM API (%s): %s", url, e)
            raise RuntimeError(f"Fallo de la API de traducción ({url}): {e}") from e

    return _call


async def translate_entries(
    entries: list[StringEntry],
    target_lang: str = "Spanish",
    api_callable: Callable[[str, str], Awaitable[str]] = default_llm_call,
    concurrency_limit: int = 10,
) -> list[StringEntry]:
    """
    Translates a list of StringEntry records concurrently with strict Fail-Fast semantics.
    Raises RuntimeError immediately if any translation fails, preventing corrupted/partial exports.
    """
    if not entries:
        return []

    semaphore = asyncio.Semaphore(concurrency_limit)

    async def _translate_single(entry: StringEntry) -> StringEntry:
        if entry.actor:
            context = f"Target language: {target_lang}. Context: Spoken by {entry.actor}."
        elif entry.is_dialog:
            context = f"Target language: {target_lang}. Context: Spoken dialogue."
        else:
            context = f"Target language: {target_lang}. Context: UI or generic text."

        async with semaphore:
            try:
                translated_text = await api_callable(entry.text, context)
            except Exception as err:
                logger.error("Error traduciendo entrada %s: %s", entry.form_id, err)
                raise RuntimeError(f"Fallo en la traducción de la entrada {entry.form_id}: {err}") from err

        return replace(entry, translated_text=translated_text)

    return list(await asyncio.gather(*[_translate_single(entry) for entry in entries]))
