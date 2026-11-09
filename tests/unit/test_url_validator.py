import pytest

from autoapply.core.exceptions import URLValidationError
from autoapply.url.validator import validate_url


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://example.com",
            "https://example.com/",
        ),
        (
            "http://example.com",
            "http://example.com/",
        ),
        (
            "https://example.com/jobs/apply",
            "https://example.com/jobs/apply",
        ),
        (
            "https://example.com/jobs?id=123",
            "https://example.com/jobs?id=123",
        ),
        (
            "  https://example.com  ",
            "https://example.com/",
        ),
    ],
)
def test_valid_urls(url, expected):
    assert validate_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "example.com",
        "javascript:alert(1)",
        "file:///C:/Windows",
        "ftp://example.com",
        "https://",
        "https:///missing-host",
        "https://user:password@example.com",
        "https://example.com:invalid",
        "https://example.com:99999",
        "https://example.com/\nmalicious",
    ],
)
def test_invalid_urls(url):
    with pytest.raises(URLValidationError):
        validate_url(url)


def test_uppercase_scheme():
    assert validate_url("HTTPS://example.com") == ("https://example.com/")
