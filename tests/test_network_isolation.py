"""
Regression tests for hermetic test network isolation.

Proves:
1. Default-deny behavior: outbound DNS, reverse DNS, TCP, UDP datagrams, and urllib are blocked.
2. External hostname resolution (getaddrinfo, gethostbyname) is blocked without live DNS.
3. Reverse DNS (gethostbyaddr, getnameinfo) for external IPs is blocked without live DNS.
4. Subdomain spoofing (e.g. 127.example.com) is rejected by semantic IP validation.
5. Real loopback (127.0.0.0/8, ::1, localhost) is permitted for in-process testing.
6. UDP datagram egress (sendto) to external literal IPs is blocked without DNS lookups.
7. Loopback UDP datagram communication functions properly.
8. Non-http(s) or missing-hostname URLs fail closed in urllib guard.
9. Guarded socket sendto/sendmsg invoke the real backend at most once on error.
10. Google Translate, OpenAI, and arbitrary external endpoints are blocked unless explicitly mocked.
11. Raw socket / non-urllib clients (http.client, socket) cannot bypass the guard.
12. Explicit test-scoped mocks (monkeypatch) work seamlessly.
13. Sensitive credentials and query parameters are stripped from error messages.
14. Network-marked tests are skipped by default unless RUN_NETWORK_TESTS=1.
15. RUN_NETWORK_TESTS=1 does not disable isolation for unmarked tests.
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
    from conftest import NetworkAccessDeniedError, _is_allowed_host, _sanitize_destination
except ImportError:
    from tests.conftest import NetworkAccessDeniedError, _is_allowed_host, _sanitize_destination

from src.free_translator import translate_free_text_sync
from src.translator import create_openai_compatible_translator


def test_arbitrary_hostname_dns_resolution_blocked():
    """Attempting DNS resolution for external hostnames must fail immediately."""
    with pytest.raises(NetworkAccessDeniedError, match="DNS resolution for 'example.invalid'"):
        socket.getaddrinfo("example.invalid", 80)

    with pytest.raises(NetworkAccessDeniedError, match="DNS resolution for 'api.openai.com'"):
        socket.gethostbyname("api.openai.com")

    with pytest.raises(NetworkAccessDeniedError, match="DNS resolution for 'translate.googleapis.com'"):
        socket.gethostbyname_ex("translate.googleapis.com")


def test_external_reverse_dns_blocked():
    """Attempting reverse DNS lookups for external IPs must fail without network resolution."""
    with pytest.raises(NetworkAccessDeniedError, match="reverse DNS lookup for '8.8.8.8'"):
        socket.gethostbyaddr("8.8.8.8")

    with pytest.raises(NetworkAccessDeniedError, match="reverse DNS lookup for"):
        socket.getnameinfo(("8.8.8.8", 80), 0)


def test_loopback_reverse_dns_allowed():
    """Reverse DNS lookups for loopback IPs are allowed by the guard."""
    try:
        res_addr = socket.gethostbyaddr("127.0.0.1")
        assert isinstance(res_addr, tuple)
    except OSError as exc:
        assert not isinstance(exc, NetworkAccessDeniedError)

    try:
        res_name = socket.getnameinfo(("127.0.0.1", 80), 0)
        assert isinstance(res_name, tuple)
    except OSError as exc:
        assert not isinstance(exc, NetworkAccessDeniedError)


def test_subdomain_spoofing_loopback_rejected():
    """Hostnames textually starting with '127.' must NOT be treated as loopback."""
    with pytest.raises(NetworkAccessDeniedError, match="DNS resolution for '127.example.com'"):
        socket.getaddrinfo("127.example.com", 80)

    with pytest.raises(NetworkAccessDeniedError, match="DNS resolution for '127.0.0.1.attacker.com'"):
        socket.getaddrinfo("127.0.0.1.attacker.com", 80)


def test_real_ipv4_and_ipv6_loopback_range_allowed():
    """Semantic IP loopback detection allows the full 127.0.0.0/8 range and IPv6 ::1."""
    assert _is_allowed_host("::1") is True
    assert _is_allowed_host("::ffff:127.0.0.1") is True

    for loopback_ip in ["127.0.0.1", "127.0.0.2", "127.255.255.254"]:
        addrinfo = socket.getaddrinfo(loopback_ip, 80)
        assert len(addrinfo) > 0


def test_localhost_resolution_allowed():
    """Resolution of literal 'localhost' is permitted for local server testing."""
    addrinfo = socket.getaddrinfo("localhost", 80)
    assert len(addrinfo) > 0


def test_unconnected_udp_sendto_external_ip_blocked():
    """UDP sendto targeting a literal external IP must be blocked without DNS lookups."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(NetworkAccessDeniedError, match="socket.sendto to"):
            sock.sendto(b"unauthorized payload", ("8.8.8.8", 53))
    finally:
        sock.close()


def test_loopback_udp_sendto_allowed():
    """UDP sendto targeting loopback (127.0.0.1) is permitted."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.settimeout(5.0)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.settimeout(5.0)
    try:
        sent_bytes = client_sock.sendto(b"loopback datagram", ("127.0.0.1", port))
        assert sent_bytes > 0
        data, _ = server_sock.recvfrom(1024)
        assert data == b"loopback datagram"
    finally:
        client_sock.close()
        server_sock.close()


def test_urlopen_missing_hostname_or_non_http_blocked():
    """URL with missing hostname or non-http(s) scheme fails closed."""
    with pytest.raises(NetworkAccessDeniedError, match="Outbound network access is disabled during unit tests"):
        urllib.request.urlopen("file:///etc/passwd")

    with pytest.raises(NetworkAccessDeniedError, match="Outbound network access is disabled during unit tests"):
        urllib.request.urlopen("http:example.com/x")

    with pytest.raises(NetworkAccessDeniedError, match="Outbound network access is disabled during unit tests"):
        urllib.request.urlopen("ftp://127.0.0.1/resource")


def test_guarded_socket_sendmsg_and_sendto_single_execution_on_oserror(monkeypatch):
    """Verify that when real sendmsg/sendto raises OSError on an allowed connected peer, it executes exactly once."""
    class FakeConnectedSocket:
        def getpeername(self):
            return ("127.0.0.1", 8080)

    call_count = {"sendmsg": 0, "sendto": 0}

    def fake_real_sendmsg(sock, buffers, ancdata=(), flags=0, address=None):
        call_count["sendmsg"] += 1
        raise OSError("Simulated sendmsg I/O error")

    def fake_real_sendto(sock, *args, **kwargs):
        call_count["sendto"] += 1
        raise OSError("Simulated sendto I/O error")

    try:
        import conftest as ct
    except ImportError:
        import tests.conftest as ct

    monkeypatch.setattr(ct, "_REAL_SOCKET_SENDMSG", fake_real_sendmsg)
    monkeypatch.setattr(ct, "_REAL_SOCKET_SENDTO", fake_real_sendto)

    fake_sock = FakeConnectedSocket()

    # Test sendmsg single invocation
    with pytest.raises(OSError, match="Simulated sendmsg I/O error"):
        ct._guarded_socket_sendmsg(fake_sock, [b"data"])
    assert call_count["sendmsg"] == 1, f"Expected 1 call to sendmsg, got {call_count['sendmsg']}"

    # Test sendto single invocation
    with pytest.raises(OSError, match="Simulated sendto I/O error"):
        ct._guarded_socket_sendto(fake_sock, b"data")
    assert call_count["sendto"] == 1, f"Expected 1 call to sendto, got {call_count['sendto']}"


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
    """Low-level socket.connect to external IP must fail immediately."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessDeniedError, match="socket.connect to"):
            sock.connect(("93.184.216.34", 80))
    finally:
        sock.close()


def test_arbitrary_socket_connect_ex_blocked_by_default():
    """Low-level socket.connect_ex to external IP must fail immediately."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessDeniedError, match="socket.connect_ex to"):
            sock.connect_ex(("93.184.216.34", 80))
    finally:
        sock.close()


def test_raw_http_client_blocked_by_guard():
    """Standard http.client (which does not use urllib.request.urlopen) is blocked."""
    conn = http.client.HTTPSConnection("example.com", timeout=2)
    try:
        with pytest.raises(NetworkAccessDeniedError):
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
    server.settimeout(5.0)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(5.0)
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
