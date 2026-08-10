import logging
from dataclasses import replace
from typing import Callable, List
from src.models import StringEntry

logger = logging.getLogger(__name__)


def default_llm_call(text: str, context: str) -> str:
    # This is a placeholder for the actual LLM API call (OpenAI/Gemini)
    return f"Translated: {text}"


def translate_entries(
    entries: List[StringEntry],
    target_lang: str,
    api_callable: Callable[[str, str], str] = default_llm_call,
) -> List[StringEntry]:
    translated_entries: List[StringEntry] = []

    for entry in entries:
        if entry.actor:
            context = f"Target language: {target_lang}. Context: Spoken by {entry.actor}."
        elif entry.is_dialog:
            context = f"Target language: {target_lang}. Context: Spoken dialogue."
        else:
            context = f"Target language: {target_lang}. Context: UI or generic text."

        try:
            translated_text = api_callable(entry.text, context)
        except Exception as err:
            logger.error(f"Error translating entry {entry.form_id}: {err}")
            translated_text = None

        translated_entries.append(replace(entry, translated_text=translated_text))

    return translated_entries

