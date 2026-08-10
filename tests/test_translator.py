from src.models import StringEntry
from src.translator import translate_entries, default_llm_call

def test_translate_entries():
    entries = [
        StringEntry(form_id="01", text="Hello", is_dialog=False),
        StringEntry(form_id="02", text="Attack!", is_dialog=True, actor="Bandit")
    ]
    
    # We will pass a simple mock translator function
    def mock_api_call(text: str, context: str) -> str:
        return f"[ES] {text}"
    
    result = translate_entries(entries, "spanish", api_callable=mock_api_call)
    
    assert result[0].translated_text == "[ES] Hello"
    assert result[1].translated_text == "[ES] Attack!"

def test_default_llm_call():
    text = "Guard"
    context = "Context: UI or generic text."
    result = default_llm_call(text, context)
    assert result == "Translated: Guard"

def test_translate_entries_empty():
    result = translate_entries([], "spanish")
    assert result == []
