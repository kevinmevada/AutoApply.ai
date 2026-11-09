# Architecture

## High-level components

```text
PySide6 UI
    |
Application Controller
    |---------------- Configuration
    |---------------- URL validation (Phase 1)
    |---------------- Browser service (Phase 1)
    |---------------- Profile service (Phase 3)
    |---------------- Local inference client (Phase 4)
    |---------------- Workflow coordinator (later phase)
    |
SQLite application history (later phase)
```

## Repository boundaries

AutoApply is a separate repository and Python package. It communicates with the existing HIVI inference service over a local HTTP API when Phase 4 is implemented. It must not import private HIVI internals or duplicate model-runtime management.

Phase 1 must work when HIVI's model service is stopped. URL validation and browser navigation do not require an LLM.

## Threading

The PySide6 GUI thread must remain responsive. Browser operations will run in a dedicated worker/service boundary and report state changes through Qt signals or queued callbacks. The exact Playwright integration approach will be selected and tested in Phase 1; do not run blocking browser calls on the GUI thread.

## Browser lifecycle

- Visible Chromium, not headless, by default.
- User can log in and complete MFA manually.
- Browser remains open until the user closes it or chooses Close Browser.
- Persistent browser profile is stored in an application data directory, not inside source control.
- Browser profile contains sensitive cookies and must be excluded from logs and Git.

## URL and navigation security

- Accept only `http` and `https` schemes.
- Reject credentials embedded in URLs.
- Reject localhost, loopback, link-local, private and other non-public IP destinations by default.
- Resolve hostnames and validate destination addresses before navigation.
- Re-check redirect destinations and newly requested navigation targets.
- Do not treat a one-time DNS lookup as sufficient protection against DNS rebinding; enforce checks at the navigation/request boundary where practical.
- Never disable browser security features to make a site work.
- Do not bypass CAPTCHA, MFA, paywalls, or access controls.

## Privacy

- Resume and profile remain local.
- Do not log form values, resume contents, cookies, authorization headers, or session tokens.
- Store browser state and application history under a user-specific data directory with restrictive permissions where supported.
- Local inference is the default. No external model API is required for Phase 1.
- Sensitive employment-authorization questions must be explicitly reviewed by the user.

## Failure handling

Errors should be typed and user-readable. Preserve diagnostic details in local logs while redacting secrets and personal data. Browser crashes and navigation timeouts must not be represented as successful loads.
