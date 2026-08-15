import asyncio
import json
import logging
from dataclasses import replace
from typing import Awaitable, Callable, List, Optional
import urllib.request
import urllib.error
from src.models import StringEntry

logger = logging.getLogger(__name__)

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
    "Soul Cairn": "El Recordatorio de las Almas",
    "Skyforge": "Forja del Cielo",
    "Daedric": "Daédrico",
    "Dragonscale": "Escamas de dragón",
    "Dragonbone": "Hueso de dragón",
    "Ebony": "Ébano",
    "Sweetroll": "Bollo dulce",
}

SKYRIM_SYSTEM_PROMPT = """Eres un traductor experto y localizador profesional para The Elder Scrolls V: Skyrim.
Tu objetivo es traducir textos, nombres y diálogos manteniendo el tono medieval/fantástico y la coherencia con el doblaje y textos oficiales en español de España (o el idioma indicado).
Reglas:
1. Respeta el lore de Skyrim y su glosario oficial (ej: Dragonborn -> Sangre de Dragón, Whiterun -> Carrera Blanca, Thane -> Thane, Jarl -> Jarl).
2. Conserva caracteres especiales de formato, placeholders ({...}, <...>), y etiquetas de Skyrim intactos.
3. Devuelve únicamente la traducción limpia, sin explicaciones ni comillas adicionales.
"""

async def default_llm_call(text: str, context: str) -> str:
    """Default fallback translation function."""
    return f"Translated: {text}"

def create_openai_compatible_translator(
    api_key: str,
    api_base: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
) -> Callable[[str, str], Awaitable[str]]:
    """Creates an async translation callable targeting any OpenAI-compatible API (OpenAI, DeepSeek, Groq, Ollama, OpenRouter)."""
    async def _call(text: str, context: str) -> str:
        if not api_key and "localhost" not in api_base and "127.0.0.1" not in api_base:
            return f"Traducido: {text}"

        url = f"{api_base.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SKYRIM_SYSTEM_PROMPT},
                {"role": "user", "content": f"{context}\nTexto a traducir:\n{text}"}
            ],
            "temperature": 0.3
        }
        
        def _request_sync():
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data["choices"][0]["message"]["content"].strip()
                
        try:
            return await asyncio.to_thread(_request_sync)
        except Exception as e:
            logger.error(f"Error calling LLM API ({url}): {e}")
            return f"Traducido: {text}"
            
    return _call


async def translate_entries(
    entries: List[StringEntry],
    target_lang: str = "Spanish",
    api_callable: Callable[[str, str], Awaitable[str]] = default_llm_call,
    concurrency_limit: int = 10
) -> List[StringEntry]:
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
                logger.error(f"Error translating entry {entry.form_id}: {err}")
                translated_text = None

        return replace(entry, translated_text=translated_text)

    return list(await asyncio.gather(*[_translate_single(entry) for entry in entries]))
