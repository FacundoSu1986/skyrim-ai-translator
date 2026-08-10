from src.models import StringEntry
from src.translator import translate_entries, default_llm_call


def test_translate_entries():
    entries = [
        StringEntry(form_id="01", text="Hello", is_dialog=False),
        StringEntry(form_id="02", text="Attack!", is_dialog=True, actor="Bandit"),
    ]

    def mock_api_call(text: str, context: str) -> str:
        return f"[ES] {text}"

    result = translate_entries(entries, "spanish", api_callable=mock_api_call)

    assert result[0].translated_text == "[ES] Hello"
    assert result[1].translated_text == "[ES] Attack!"


def test_translate_entries_purity():
    original_entry = StringEntry(form_id="01", text="Hello", is_dialog=False)
    entries = [original_entry]

    def mock_api_call(text: str, context: str) -> str:
        return f"[ES] {text}"

    result = translate_entries(entries, "spanish", api_callable=mock_api_call)

    # Function should return a new list with new StringEntry instances (immutability)
    assert result is not entries
    assert result[0] is not original_entry
    assert original_entry.translated_text is None
    assert result[0].translated_text == "[ES] Hello"


def test_translate_entries_target_lang_and_context():
    captured_contexts = []

    def mock_api_call(text: str, context: str) -> str:
        captured_contexts.append(context)
        return f"[FR] {text}"

    entries = [
        StringEntry(form_id="01", text="Welcome", is_dialog=False),
        StringEntry(form_id="02", text="Who goes there?", is_dialog=True, actor="Guard"),
        StringEntry(form_id="03", text="Help me!", is_dialog=True, actor=None),
    ]

    translate_entries(entries, "french", api_callable=mock_api_call)

    assert len(captured_contexts) == 3
    assert "Target language: french." in captured_contexts[0]
    assert "Context: UI or generic text." in captured_contexts[0]

    assert "Target language: french." in captured_contexts[1]
    assert "Context: Spoken by Guard." in captured_contexts[1]

    assert "Target language: french." in captured_contexts[2]
    assert "Context: Spoken dialogue." in captured_contexts[2]


def test_translate_entries_batch_error_handling():
    def mock_api_call_with_error(text: str, context: str) -> str:
        if text == "FailMe":
            raise RuntimeError("API Connection Error")
        return f"[ES] {text}"

    entries = [
        StringEntry(form_id="01", text="Hello", is_dialog=False),
        StringEntry(form_id="02", text="FailMe", is_dialog=False),
        StringEntry(form_id="03", text="Goodbye", is_dialog=False),
    ]

    result = translate_entries(entries, "spanish", api_callable=mock_api_call_with_error)

    assert len(result) == 3
    assert result[0].translated_text == "[ES] Hello"
    assert result[1].translated_text is None
    assert result[2].translated_text == "[ES] Goodbye"


def test_default_llm_call():
    text = "Guard"
    context = "Context: UI or generic text."
    result = default_llm_call(text, context)
    assert result == "Translated: Guard"


def test_translate_entries_empty():
    result = translate_entries([], "spanish")
    assert result == []

