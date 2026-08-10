from typing import Callable, List
from src.models import StringEntry

def default_llm_call(text: str, context: str) -> str:
    # This is a placeholder for the actual LLM API call (OpenAI/Gemini)
    return f"Translated: {text}"

def translate_entries(entries: List[StringEntry], target_lang: str, api_callable: Callable = default_llm_call) -> List[StringEntry]:
    for entry in entries:
        context = f"Context: This is spoken by {entry.actor}." if entry.actor else "Context: UI or generic text."
        entry.translated_text = api_callable(entry.text, context)
    return entries
