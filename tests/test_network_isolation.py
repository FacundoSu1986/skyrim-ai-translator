"""
Regression tests for hermetic test network isolation.

Proves:
1. Default-deny behavior: outbound urllib and socket connections are blocked.
2. Google Translate, OpenAI, and arbitrary external endpoints are blocked unless explicitly mocked.
3. Raw socket / non-urllib clients (http.client, socket) cannot bypass the guard.
4. Loopback (127.0.0.1, ::1, localhost) is permitted for in-process testing.
5. Explicit test-scoped mocks (monkeypatch) work seamlessly.
6. Sensitive credentials and query parameters are stripped from error messages.
7. Network-marked tests are skipped by default unless RUN_NETWORK_TESTS=1.
8. RUN_NETWORK_TESTS=1 does not disable isolation for unmarked tests.
"""

import http.client
import io
import json
import os
import socket
import urllib.parse
import urllib.request
import pytest

try:
    from conftest import NetworkAccessDeniedError, _sanitize_destination
except ImportError:
    from tests.conftest import NetworkAccessDeniedError, _sanitize_destination

from src.free_translator import translate_free_text_sync
from src.translator import create_openai_compatible_translator


def test_arbitrary_https_urlopen_blocked_by_default():
    """Attempting outbound HTTPS via urllib without a mock must fail immediately."""
    with pytest.raises(NetworkAccessDeniedError, match="Outbound network access is disabled during unit tests"):
        urllib.request.urlopen("https://example.invalid/")


def test_arbitrary_http_urlopen_blocked_by_default():
    """Attempting outbound HTTP via urllib without a mock must fail immediately."""
    with pytest.raises(NetworkAccessDeniedError, match="Outbound network access is disabled during unit tests"):
        urllib.request.urlopen("http://example.com/api/v1/test")


def test_unmocked_google_translate_blocked_by_default():
    """Calling free_translator without an explicit mock must fail due to network isolation."""
    with pytest.raises(RuntimeError, match="Fallo del traductor gratuito"):
        translate_free_text_sync("Hello Dragonborn")


@pytest.mark.asyncio
async def test_unmocked_openai_translator_blocked_by_default():
    """Calling OpenAI translator without an explicit mock must fail due to network isolation."""
    translator = create_openai_compatible_translator(
        api_key="sk-test-secret-key",
        api_base="https://api.openai.com/v1",
    )
    with pytest.raises(RuntimeError, match="Fallo de la API de traducción"):
        await translator("Hello", "Context: dialog")


def test_arbitrary_socket_connect_blocked_by_default():
    """Low-level socket.connect to external host/IP must fail immediately."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessDeniedError, match="socket.connect to"):
            sock.connect(("93.184.216.34", 80))
    finally:
        sock.close()


def test_arbitrary_socket_connect_ex_blocked_by_default():
    """Low-level socket.connect_ex to external host/IP must fail immediately."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessDeniedError, match="socket.connect_ex to"):
            sock.connect_ex(("93.184.216.34", 80))
    finally:
        sock.close()


def test_raw_http_client_blocked_by_socket_guard():
    """Standard http.client (which does not use urllib.request.urlopen) is blocked by socket guard."""
    conn = http.client.HTTPSConnection("example.com", timeout=2)
    try:
        with pytest.raises(NetworkAccessDeniedError, match="socket.connect"):
            conn.request("GET", "/")
    finally:
        conn.close()


def test_explicit_mock_allows_test_to_pass(monkeypatch):
    """Explicitly mocking urllib.request.urlopen takes precedence and executes cleanly."""
    class MockResponse:
        def read(self):
            return b'{"result": "mocked"}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, *args, **kwargs: MockResponse())

    resp = urllib.request.urlopen("https://api.example.com/data")
    assert resp.read() == b'{"result": "mocked"}'


def test_loopback_connection_permitted():
    """Local loopback socket connections (127.0.0.1) are permitted for in-process servers/testing."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", port))
        conn, _ = server.accept()
        conn.close()
    finally:
        client.close()
        server.close()


def test_url_sanitization_masks_sensitive_data():
    """Destination sanitization must remove query parameters, credentials, and fragments."""
    raw_url = "https://user:password123@api.openai.com:8443/v1/chat/completions?key=sk-secret#anchor"
    sanitized = _sanitize_destination(raw_url)
    assert sanitized == "https://api.openai.com:8443/v1/chat/completions"
    assert "password123" not in sanitized
    assert "sk-secret" not in sanitized
    assert "key=" not in sanitized
    assert "user:" not in sanitized


@pytest.mark.network
def test_network_marker_skips_by_default():
    """Tests marked with @pytest.mark.network must be skipped when RUN_NETWORK_TESTS is not 1."""
    # If this runs, it means RUN_NETWORK_TESTS was set to 1.
    # When RUN_NETWORK_TESTS is unset/0, pytest will skip before entering this body.
    assert os.environ.get("RUN_NETWORK_TESTS") == "1"


def test_unmarked_test_blocked_even_when_run_network_tests_is_set(monkeypatch):
    """An unmarked test remains blocked from outbound network even if RUN_NETWORK_TESTS=1 is in env."""
    monkeypatch.setenv("RUN_NETWORK_TESTS", "1")
    with pytest.raises(NetworkAccessDeniedError, match="Outbound network access is disabled during unit tests"):
        urllib.request.urlopen("https://example.invalid/")
