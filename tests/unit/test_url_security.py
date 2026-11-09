import socket

import pytest

from autoapply.core.exceptions import URLValidationError
from autoapply.url.security import validate_public_url


def fake_resolver(addresses):
    def resolve(host, port, type):
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, port),
            )
            for address in addresses
        ]

    return resolve


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.1.1",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fe80::1",
        "100.64.0.1",
        "224.0.0.1",
    ],
)
def test_rejects_non_public_ip_literals(address):
    if ":" in address:
        url = f"https://[{address}]/"
    else:
        url = f"https://{address}/"
    with pytest.raises(URLValidationError):
        validate_public_url(url, resolver=fake_resolver([]))


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/",
        "https://LOCALHOST/",
        "https://app.localhost/",
        "https://printer.local/",
        "https://service.internal/",
        "https://fixture.test/",
    ],
)
def test_rejects_local_hostnames(url):
    with pytest.raises(URLValidationError):
        validate_public_url(url, resolver=fake_resolver(["1.1.1.1"]))


def test_rejects_dns_failure():
    def broken_resolver(host, port, type):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    with pytest.raises(URLValidationError, match="Unable to resolve"):
        validate_public_url(
            "https://missing.example/",
            resolver=broken_resolver,
        )


def test_rejects_empty_resolution():
    with pytest.raises(URLValidationError, match="Unable to resolve"):
        validate_public_url(
            "https://empty.example/",
            resolver=fake_resolver([]),
        )


def test_rejects_mixed_public_and_private_addresses():
    with pytest.raises(URLValidationError):
        validate_public_url(
            "https://mixed.example/",
            resolver=fake_resolver(["8.8.8.8", "10.0.0.1"]),
        )


def test_rejects_hostname_resolving_only_to_private():
    with pytest.raises(URLValidationError):
        validate_public_url(
            "https://intranet.example/",
            resolver=fake_resolver(["192.168.1.50"]),
        )


def test_allows_public_ipv4_literal():
    assert (
        validate_public_url(
            "https://1.1.1.1/careers",
            resolver=fake_resolver([]),
        )
        == "https://1.1.1.1/careers"
    )


def test_allows_public_ipv6_literal():
    assert (
        validate_public_url(
            "https://[2606:4700:4700::1111]/",
            resolver=fake_resolver([]),
        )
        == "https://[2606:4700:4700::1111]/"
    )


def test_allows_hostname_with_only_public_addresses():
    assert (
        validate_public_url(
            "https://example.com/jobs",
            resolver=fake_resolver(["93.184.216.34", "2606:2800:220:1::248"]),
        )
        == "https://example.com/jobs"
    )


def test_still_rejects_invalid_syntax():
    with pytest.raises(URLValidationError):
        validate_public_url(
            "javascript:alert(1)",
            resolver=fake_resolver(["1.1.1.1"]),
        )
