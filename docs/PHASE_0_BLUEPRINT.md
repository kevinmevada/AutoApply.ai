# Phase 0 — Blueprint and Repository Foundation

## Goal

Create a clean, independently testable project foundation for HIVI AutoApply. Phase 0 must not launch a browser, inspect forms, load a resume, call an LLM, or submit an application.

## Product boundary

**Input:** A URL supplied by the user.

**Initial outcome (Phase 1):** A visible browser opens that URL after validation.

**Later outcome:** The application may populate fields from a locally stored profile and attach the user's existing resume. It must stop before final submission.

### Explicitly excluded

- Job discovery or scraping job boards for openings
- Resume rewriting, optimization, or generation
- ATS scoring
- Cover-letter generation
- Automated final submission
- CAPTCHA or access-control bypass

## Phase 0 deliverables

1. Standalone repository and Python package.
2. Dependency and development-tool declarations.
3. Central YAML configuration.
4. Architecture and security decisions.
5. Logging conventions.
6. Test organization.
7. Local-data and secret-handling rules.

## Proposed phases

- **P0:** Blueprint, package structure, configuration and test foundation.
- **P1:** URL validation, visible Chromium launch, navigation, status and error handling.
- **P2:** Read-only page inspection and form-field extraction.
- **P3:** Local profile and existing PDF resume integration.
- **P4:** Local model integration for interpreting ambiguous fields.
- **P5:** Form filling and file upload.
- **P6:** Multi-step form handling and recovery.
- **P7:** Verification and final review; user submits manually.
- **P8:** Desktop UI polish, history and packaging.

## Phase 0 acceptance criteria

- [ ] Package and directory structure exist.
- [ ] Project dependencies are declared.
- [ ] Configuration schema and defaults are documented.
- [ ] Module boundaries are documented.
- [ ] Security and privacy decisions are documented.
- [ ] Test layout and commands are documented.
- [ ] No Phase 1 browser functionality has been implemented.
