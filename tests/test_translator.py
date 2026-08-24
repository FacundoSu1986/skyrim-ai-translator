import asyncio
import pytest
from src.models import StringEntry
from src.translator import translate_entries, default_llm_call


@pytest.mark.asyncio
async def test_translate_entries():
    entries = [
        StringEntry(form_id="01", text="Hello", is_dialog=False),
        StringEntry(form_id="02", text="Attack!", is_dialog=True, actor="Bandit"),
    ]

    async def mock_api_call(text: str, context: str) -> str:
        return f"[ES] {text}"

    result = await translate_entries(entries, "spanish", api_callable=mock_api_call)

    assert result[0].translated_text == "[ES] Hello"
    assert result[1].translated_text == "[ES] Attack!"


@pytest.mark.asyncio
async def test_translate_entries_purity():
    original_entry = StringEntry(form_id="01", text="Hello", is_dialog=False)
    entries = [original_entry]

    async def mock_api_call(text: str, context: str) -> str:
        return f"[ES] {text}"

    result = await translate_entries(entries, "spanish", api_callable=mock_api_call)

    # Function should return a new list with new StringEntry instances (immutability)
    assert result is not entries
    assert result[0] is not original_entry
    assert original_entry.translated_text is None
    assert result[0].translated_text == "[ES] Hello"


@pytest.mark.asyncio
async def test_translate_entries_target_lang_and_context():
    captured_contexts = []

    async def mock_api_call(text: str, context: str) -> str:
        captured_contexts.append(context)
        return f"[FR] {text}"

    entries = [
        StringEntry(form_id="01", text="Welcome", is_dialog=False),
        StringEntry(form_id="02", text="Who goes there?", is_dialog=True, actor="Guard"),
        StringEntry(form_id="03", text="Help me!", is_dialog=True, actor=None),
    ]

    await translate_entries(entries, "french", api_callable=mock_api_call)

    assert len(captured_contexts) == 3
    assert "Target language: french." in captured_contexts[0]
    assert "Context: UI or generic text." in captured_contexts[0]

    assert "Target language: french." in captured_contexts[1]
    assert "Context: Spoken by Guard." in captured_contexts[1]

    assert "Target language: french." in captured_contexts[2]
    assert "Context: Spoken dialogue." in captured_contexts[2]


@pytest.mark.asyncio
async def test_translate_entries_batch_error_handling():
    async def mock_api_call_with_error(text: str, context: str) -> str:
        if text == "FailMe":
            raise RuntimeError("API Connection Error")
        return f"[ES] {text}"

    entries = [
        StringEntry(form_id="01", text="Hello", is_dialog=False),
        StringEntry(form_id="02", text="FailMe", is_dialog=False),
        StringEntry(form_id="03", text="Goodbye", is_dialog=False),
    ]

    # Fail-Fast: Any individual translation failure must raise RuntimeError to prevent corrupted partial exports
    with pytest.raises(RuntimeError, match="Fallo en la traducción de la entrada 02"):
        await translate_entries(entries, "spanish", api_callable=mock_api_call_with_error)


@pytest.mark.asyncio
async def test_default_llm_call():
    text = "Guard"
    context = "Context: UI or generic text."
    result = await default_llm_call(text, context)
    assert result == "Translated: Guard"


@pytest.mark.asyncio
async def test_translate_entries_empty():
    result = await translate_entries([], "spanish")
    assert result == []


@pytest.mark.asyncio
async def test_translate_entries_concurrency():
    active_calls = 0
    max_active_calls = 0

    async def mock_api_call(text: str, context: str) -> str:
        nonlocal active_calls, max_active_calls
        active_calls += 1
        if active_calls > max_active_calls:
            max_active_calls = active_calls
        await asyncio.sleep(0.01)
        active_calls -= 1
        return f"[ES] {text}"

    entries = [StringEntry(form_id=str(i), text=f"Text {i}") for i in range(15)]
    result = await translate_entries(entries, "spanish", api_callable=mock_api_call)

    assert len(result) == 15
    assert max_active_calls <= 10
    assert max_active_calls > 1


def test_skyrim_glossary_entries():
    from src.translator import SKYRIM_GLOSSARY
    assert "Dragonborn" in SKYRIM_GLOSSARY
    assert SKYRIM_GLOSSARY["Dragonborn"] == "Sangre de Dragón"
    assert SKYRIM_GLOSSARY["Whiterun"] == "Carrera Blanca"
    assert SKYRIM_GLOSSARY["Blackreach"] == "Límite Sombrío"
    assert SKYRIM_GLOSSARY["Soul Cairn"] == "Recordatorio de las Almas"
    assert SKYRIM_GLOSSARY["Sweetroll"] == "Bollo dulce"
    assert SKYRIM_GLOSSARY["Solstheim"] == "Solstheim"
    assert SKYRIM_GLOSSARY["Raven Rock"] == "Roca del Cuervo"
    assert SKYRIM_GLOSSARY["Tel Mithryn"] == "Tel Mithryn"
    assert SKYRIM_GLOSSARY["Skyforge"] == "Forja del Cielo"


@pytest.mark.asyncio
async def test_openai_compatible_translator_no_key():
    from src.translator import create_openai_compatible_translator
    fn = create_openai_compatible_translator(api_key="")
    with pytest.raises(RuntimeError, match="api_key"):
        await fn("Sword", "Context: weapon")


@pytest.mark.asyncio
async def test_openai_compatible_translator_mock_success(monkeypatch):
    import io
    import json
    from src.translator import create_openai_compatible_translator

    fake_response_data = {
        "choices": [{"message": {"content": "Espada de hierro"}}]
    }

    class MockResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps(fake_response_data).encode("utf-8"))
        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=30):
        return MockResponse()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    fn = create_openai_compatible_translator(api_key="sk-test-key", api_base="https://api.openai.com/v1", model="gpt-4o-mini")
    res = await fn("Iron Sword", "Context: weapon")
    assert res == "Espada de hierro"


@pytest.mark.asyncio
async def test_openai_compatible_translator_mock_error(monkeypatch):
    from src.translator import create_openai_compatible_translator

    def mock_urlopen_error(req, timeout=30):
        raise urllib.error.URLError("Network unreachable")

    import urllib.request
    import urllib.error
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_error)

    fn = create_openai_compatible_translator(api_key="sk-test-key")
    with pytest.raises(RuntimeError, match="Fallo de la API"):
        await fn("Iron Sword", "Context: weapon")


@pytest.mark.asyncio
async def test_openai_compatible_translator_includes_glossary_in_payload(monkeypatch):
    import io
    import json
    import urllib.request
    from src.translator import create_openai_compatible_translator

    captured_payload = None

    class MockResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": "Traducido"}}]}).encode("utf-8"))
        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=30):
        nonlocal captured_payload
        captured_payload = json.loads(req.data.decode("utf-8"))
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    fn = create_openai_compatible_translator(api_key="sk-test-key")
    await fn("Travel to Whiterun", "Context: Quest")

    assert captured_payload is not None
    system_msg = captured_payload["messages"][0]["content"]
    assert "Whiterun -> Carrera Blanca" in system_msg
    assert "Blackreach -> Límite Sombrío" in system_msg
    assert "Soul Cairn -> Recordatorio de las Almas" in system_msg


@pytest.mark.asyncio
async def test_openai_compatible_translator_non_spanish_isolation(monkeypatch):
    import io
    import json
    import urllib.request
    from src.translator import create_openai_compatible_translator

    captured_payload = None

    class MockResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": "Voyage à Blancherive"}}]}).encode("utf-8"))
        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=30):
        nonlocal captured_payload
        captured_payload = json.loads(req.data.decode("utf-8"))
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    fn = create_openai_compatible_translator(api_key="sk-test-key", target_lang="French")
    await fn("Travel to Whiterun", "Target language: French. Context: Quest")

    assert captured_payload is not None
    system_msg = captured_payload["messages"][0]["content"]
    # French system prompt must NOT contain Spanish glossary lines
    assert "Carrera Blanca" not in system_msg
    assert "Sangre de Dragón" not in system_msg
    assert "French" in system_msg


def test_translation_provider_enum():
    from src.translator import TranslationProvider
    assert TranslationProvider.OPENAI_COMPATIBLE == "openai_compatible"
    assert TranslationProvider.OLLAMA == "ollama"
    assert TranslationProvider.UNOFFICIAL_GTX == "unofficial_gtx"


def test_free_translator_transparent_user_agent(monkeypatch):
    import io
    import json
    import urllib.request
    from src.free_translator import translate_free_text_sync

    captured_request = None

    class MockResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps([[["Hola mundo", "Hello world"]]]).encode("utf-8"))

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=10):
        nonlocal captured_request
        captured_request = req
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    result = translate_free_text_sync("Hello world", "Spanish")
    assert result == "Hola mundo"
    assert captured_request is not None
    user_agent = captured_request.get_header("User-agent")
    assert user_agent == "skyrim-ai-translator/1.0 (https://github.com/FacundoSu1986/skyrim-ai-translator)"


def test_free_translator_warning_emitted_once_per_process(monkeypatch):
    import io
    import json
    import urllib.request
    import warnings
    import src.free_translator
    from src.free_translator import translate_free_text_sync

    class MockResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps([[["Texto traducido", "Translated text"]]]).encode("utf-8"))

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=10):
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(src.free_translator, "_warned_unofficial_gtx", False)

    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        result1 = translate_free_text_sync("First sentence", "Spanish")
        assert result1 == "Texto traducido"
        assert len(recorded_warnings) == 1
        warning_msg = str(recorded_warnings[0].message)
        assert "GTX" in warning_msg
        assert "SLA" in warning_msg
        assert issubclass(recorded_warnings[0].category, UserWarning)

    with warnings.catch_warnings(record=True) as recorded_warnings_2:
        warnings.simplefilter("always")
        result2 = translate_free_text_sync("Second sentence", "Spanish")
        assert result2 == "Texto traducido"
        assert len(recorded_warnings_2) == 0

    assert src.free_translator._warned_unofficial_gtx is True


def test_free_translator_empty_text_no_network_no_warning(monkeypatch):
    import src.free_translator
    from src.free_translator import translate_free_text_sync

    monkeypatch.setattr(src.free_translator, "_warned_unofficial_gtx", False)
    res = translate_free_text_sync("", "Spanish")
    assert res == ""
    assert src.free_translator._warned_unofficial_gtx is False

    res_ws = translate_free_text_sync("   ", "Spanish")
    assert res_ws == "   "
    assert src.free_translator._warned_unofficial_gtx is False


def test_free_translator_glossary_protection_flow(monkeypatch):
    import io
    import json
    import urllib.parse
    import urllib.request
    from src.free_translator import translate_free_text_sync

    captured_url = None

    class MockResponse:
        def __init__(self, query_text: str):
            self.query_text = query_text

        def __enter__(self):
            # Google Translate returns the text with placeholders preserved
            translated_query = self.query_text.replace("Travel to", "Viaja a").replace("today", "hoy")
            return io.BytesIO(json.dumps([[[translated_query, self.query_text]]]).encode("utf-8"))

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=10):
        nonlocal captured_url
        captured_url = req.full_url
        parsed = urllib.parse.urlparse(req.full_url)
        q_val = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
        return MockResponse(q_val)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    result = translate_free_text_sync("Travel to Whiterun today", "Spanish")
    assert result == "Viaja a Carrera Blanca hoy"
    assert captured_url is not None
    assert "__SKY_" in captured_url


def test_free_translator_error_handling(monkeypatch):
    import urllib.error
    import urllib.request
    from src.free_translator import translate_free_text_sync

    def mock_urlopen_fail(req, timeout=10):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_fail)

    with pytest.raises(RuntimeError, match="Fallo del traductor gratuito"):
        translate_free_text_sync("Hello world", "Spanish")


@pytest.mark.asyncio
async def test_free_translator_callable_and_create(monkeypatch):
    import io
    import json
    import urllib.request
    from src.free_translator import create_free_translator, free_translator_callable

    class MockResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps([[["Bonjour", "Hello"]]]).encode("utf-8"))

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=10):
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    custom_fn = create_free_translator(target_lang="French")
    res1 = await custom_fn("Hello", "Context: UI")
    assert res1 == "Bonjour"

    res2 = await free_translator_callable("Hello", "Target language: French. Context: UI")
    assert res2 == "Bonjour"






