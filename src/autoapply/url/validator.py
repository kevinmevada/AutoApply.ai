"""URL validation and normalization."""

from urllib.parse import urlsplit, urlunsplit

from autoapply.core.exceptions import URLValidationError

ALLOWED_SCHEMES = frozenset({"http", "https"})


def validate_url(raw_url: str) -> str:
    """Validate and normalize a user-supplied HTTP(S) URL.

    Raises:
        URLValidationError: If the URL is empty, malformed, or disallowed.
    """
    if raw_url is None or not str(raw_url).strip():
        raise URLValidationError("Please enter a URL.")

    value = raw_url.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise URLValidationError("URL contains invalid control characters.")

    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        if scheme not in ALLOWED_SCHEMES:
            raise URLValidationError("Only HTTP and HTTPS URLs are supported.")
        if not parsed.netloc or not parsed.hostname:
            raise URLValidationError("URL must contain a valid hostname.")
        if parsed.username is not None or parsed.password is not None:
            raise URLValidationError("URLs containing embedded credentials are not allowed.")

        # Accessing port also validates malformed port numbers.
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            raise URLValidationError("Invalid port number.")

        # Validate IDNA encoding; authority casing is preserved in netloc.
        parsed.hostname.encode("idna").decode("ascii").lower()

        return urlunsplit(
            (
                scheme,
                parsed.netloc,
                parsed.path or "/",
                parsed.query,
                parsed.fragment,
            )
        )
    except URLValidationError:
        raise
    except (ValueError, UnicodeError) as exc:
        raise URLValidationError("URL is malformed.") from exc
