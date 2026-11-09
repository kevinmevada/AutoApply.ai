"""Navigation destination security policy."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

from autoapply.core.exceptions import URLValidationError
from autoapply.url.validator import validate_url

LOCAL_HOSTNAMES = frozenset({"localhost"})
LOCAL_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".test",
)

Resolver = Callable[..., list]


def _is_public_ip(address: str) -> bool:
    """Return True only for globally routable IP addresses."""
    try:
        ip = ipaddress.ip_address(address.split("%")[0])
    except ValueError:
        return False
    # Python treats some multicast addresses as is_global=True; reject them.
    return ip.is_global and not ip.is_multicast


def _is_blocked_hostname(hostname: str) -> bool:
    host = hostname.lower().rstrip(".")
    if host in LOCAL_HOSTNAMES:
        return True
    return any(host.endswith(suffix) for suffix in LOCAL_SUFFIXES)


def _addresses_from_results(results: list) -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()
    for result in results:
        sockaddr = result[4]
        address = sockaddr[0]
        if address not in seen:
            seen.add(address)
            addresses.append(address)
    return addresses


def validate_public_url(
    raw_url: str,
    resolver: Resolver = socket.getaddrinfo,
) -> str:
    """Validate a URL and reject destinations that are not publicly routable.

    Performs P1.2 syntax validation, then rejects local hostnames and any
    destination whose resolved addresses are not entirely globally routable.
    """
    normalized = validate_url(raw_url)
    parsed = urlsplit(normalized)
    hostname = parsed.hostname
    if hostname is None:
        raise URLValidationError("URL must contain a valid hostname.")

    if _is_blocked_hostname(hostname):
        raise URLValidationError("Local and internal hostnames are not allowed.")

    try:
        ipaddress.ip_address(hostname)
        is_literal_ip = True
    except ValueError:
        is_literal_ip = False

    if is_literal_ip:
        if not _is_public_ip(hostname):
            raise URLValidationError(
                "URLs targeting private or non-public IP addresses are not allowed."
            )
        return normalized

    try:
        results = resolver(hostname, parsed.port or 0, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise URLValidationError("Unable to resolve the destination hostname.") from exc

    addresses = _addresses_from_results(results)
    if not addresses:
        raise URLValidationError("Unable to resolve the destination hostname.")

    if not all(_is_public_ip(address) for address in addresses):
        raise URLValidationError(
            "URLs targeting private or non-public IP addresses are not allowed."
        )

    return normalized
