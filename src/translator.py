import asyncio
import logging
from dataclasses import replace
from typing import Awaitable, Callable, List
from src.models import StringEntry

logger = logging.getLogger(__name__)


async def default_llm_call(text: str, context: str) -> str:
    # This is a placeholder for the actual LLM API call (OpenAI/Gemini)
    return f"Translated: {text}"


async def translate_entries(
    entries: List[StringEntry],
    target_lang: str,
    api_callable: Callable[[str, str], Awaitable[str]] = default_llm_call,
) -> List[StringEntry]:
    if not entries:
        return []

    semaphore = asyncio.Semaphore(10)

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


