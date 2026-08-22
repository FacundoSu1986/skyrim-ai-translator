"""
Global test configuration and hermetic network guard.

Enforces default-deny outbound network access across the entire test suite.
Any unexpected external network request immediately raises NetworkAccessDeniedError.
Local loopback traffic (127.0.0.1, ::1, localhost) is permitted for in-process testing.
Live integration tests requiring actual network access must be explicitly marked with
@pytest.mark.network and opted into via RUN_NETWORK_TESTS=1.
"""

import ipaddress
import os
import socket
import urllib.parse
import urllib.request
from typing import Any, Optional, Union

import pytest


class NetworkAccessDeniedError(RuntimeError):
    """Raised when test code attempts unauthorized outbound network access."""


_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_GETHOSTBYNAME = socket.gethostbyname
_REAL_GETHOSTBYNAME_EX = socket.gethostbyname_ex
_REAL_URLOPEN = urllib.request.urlopen
_REAL_SOCKET_CONNECT = socket.socket.connect
_REAL_SOCKET_CONNECT_EX = socket.socket.connect_ex


def _sanitize_destination(destination: Any) -> str:
    """
    Sanitizes destination to scheme + hostname + port + path.
    Strips query parameters, fragment, credentials, and headers to prevent
    leaking sensitive API keys, tokens, or credentials in test logs.
    """
    try:
        url_str = destination.full_url if hasattr(destination, "full_url") else str(destination)
        parsed = urllib.parse.urlparse(url_str)
        if parsed.scheme:
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            path = parsed.path or "/"
            return f"{parsed.scheme}://{host}{port}{path}"
    except Exception:
        pass
    return str(destination)


def _is_allowed_host(host: Optional[str]) -> bool:
    """
    Validates whether host is an authorized local loopback destination.
    Uses semantic IP validation with ipaddress to prevent partial-match spoofing
    (e.g., '127.example.com').
    """
    if host is None:
        return True
    normalized = str(host).strip().lower()
    if normalized in ("", "localhost"):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
        is_mapped_loopback = (
            ip.ipv4_mapped and ip.ipv4_mapped.is_loopback
            if hasattr(ip, "ipv4_mapped") and ip.ipv4_mapped
            else False
        )
        return ip.is_loopback or is_mapped_loopback
    except ValueError:
        return False


def _is_allowed_socket_address(address: Any) -> bool:
    if isinstance(address, tuple) and address:
        host = str(address[0])
        return _is_allowed_host(host)
    if isinstance(address, (str, bytes)):
        addr_str = address.decode("utf-8", errors="ignore") if isinstance(address, bytes) else str(address)
        if addr_str.startswith("\x00") or addr_str.startswith("/") or _is_allowed_host(addr_str):
            return True
    return False


def _guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_allowed_host(host):
        return _REAL_GETADDRINFO(host, port, *args, **kwargs)

    sanitized = _sanitize_destination(host)
    raise NetworkAccessDeniedError(
        f"Outbound network access is disabled during unit tests: DNS resolution for {sanitized!r}"
    )


def _guarded_gethostbyname(hostname: Any) -> str:
    if _is_allowed_host(hostname):
        return _REAL_GETHOSTBYNAME(hostname)

    sanitized = _sanitize_destination(hostname)
    raise NetworkAccessDeniedError(
        f"Outbound network access is disabled during unit tests: DNS resolution for {sanitized!r}"
    )


def _guarded_gethostbyname_ex(hostname: Any) -> Any:
    if _is_allowed_host(hostname):
        return _REAL_GETHOSTBYNAME_EX(hostname)

    sanitized = _sanitize_destination(hostname)
    raise NetworkAccessDeniedError(
        f"Outbound network access is disabled during unit tests: DNS resolution for {sanitized!r}"
    )


def _guarded_urlopen(req: Union[str, urllib.request.Request], *args: Any, **kwargs: Any) -> Any:
    url = req.full_url if hasattr(req, "full_url") else str(req)
    parsed = urllib.parse.urlparse(url)
    if _is_allowed_host(parsed.hostname):
        return _REAL_URLOPEN(req, *args, **kwargs)

    sanitized = _sanitize_destination(req)
    raise NetworkAccessDeniedError(
        f"Outbound network access is disabled during unit tests: {sanitized}"
    )


def _guarded_socket_connect(self: socket.socket, address: Any) -> Any:
    if _is_allowed_socket_address(address):
        return _REAL_SOCKET_CONNECT(self, address)

    sanitized = _sanitize_destination(address)
    raise NetworkAccessDeniedError(
        f"Outbound network access is disabled during unit tests: socket.connect to {sanitized}"
    )


def _guarded_socket_connect_ex(self: socket.socket, address: Any) -> int:
    if _is_allowed_socket_address(address):
        return _REAL_SOCKET_CONNECT_EX(self, address)

    sanitized = _sanitize_destination(address)
    raise NetworkAccessDeniedError(
        f"Outbound network access is disabled during unit tests: socket.connect_ex to {sanitized}"
    )


@pytest.fixture(autouse=True)
def hermetic_network_guard(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """
    Default-deny network isolation fixture.

    Invariant:
    - Normal tests: outbound network is blocked by default (DNS, socket, and urllib).
    - Network tests (@pytest.mark.network):
        - If RUN_NETWORK_TESTS=1: network access is permitted for this test only.
        - If RUN_NETWORK_TESTS!=1: the test is skipped deterministically.
    - Explicit unit test mocks (e.g. monkeypatch.setattr) take precedence within the test scope.
    """
    has_network_marker = request.node.get_closest_marker("network") is not None
    if has_network_marker:
        if os.environ.get("RUN_NETWORK_TESTS") == "1":
            return
        pytest.skip("Live network test skipped: RUN_NETWORK_TESTS=1 is not set")

    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", _guarded_gethostbyname)
    monkeypatch.setattr(socket, "gethostbyname_ex", _guarded_gethostbyname_ex)
    monkeypatch.setattr(socket.socket, "connect", _guarded_socket_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_socket_connect_ex)
    monkeypatch.setattr(urllib.request, "urlopen", _guarded_urlopen)
