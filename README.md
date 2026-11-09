# HIVI AutoApply

A standalone, local-first Windows desktop application for filling user-provided job application forms using an existing resume and locally stored profile information.

## Scope

The first release is intentionally narrow:

1. User supplies an application URL.
2. AutoApply opens it in a visible, controlled browser.
3. Later phases inspect and fill the form using the user's existing profile and resume.
4. The application stops at final review. The user submits manually.

Out of scope: job discovery, resume rewriting, ATS scoring, cover-letter generation, and automatic final submission.

## Phase 0

Phase 0 establishes the repository structure, configuration contract, architecture decisions, and test layout. It does not implement browser automation or call an LLM.

See `docs/PHASE_0_BLUEPRINT.md` and `docs/ARCHITECTURE.md`.

## Development setup (Windows PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Playwright browser installation will be performed in Phase 1:

```powershell
playwright install chromium
```

## Run tests

```powershell
pytest
```

## Configuration

The starter configuration is `configs/autoapply.yaml`. Paths are relative to the project root unless documented otherwise. Do not commit personal profile data, resumes, browser sessions, cookies, or application records.
