# SUBMISSION Testing Summary (CW1)

This document provides evidence of automated API testing for the SmartAgri Guide Flask backend.

## Test Framework and Scope

- Framework: `pytest`
- Test location: `tests/`
- Current suites:
  - `tests/test_auth.py`
  - `tests/test_farms.py`

## How to Run

From the project root:

```powershell
c:/Users/ratul/SmartAgri-Guide/.venv/Scripts/python.exe -m pytest -q
```

## Latest Execution Result

- Result: **6 passed, 0 failed**
- Covered domains:
  - Account creation and login verification gating
  - JWT logout blacklist flow
  - Protected endpoint access control
  - Authenticated farm creation
  - Admin-only farm deletion

## Criteria Mapping (CW1)

- Evidence of automated API testing: covered by repeatable `pytest` test runs.
- Authentication behavior: verified with login, verified-user checks, and logout blacklist tests.
- REST endpoint reliability: key farm CRUD pathways and authorization constraints are validated.

## Assessor Note

For submission packaging, this markdown can be exported to PDF and included with:
- endpoint summary
- Postman run output screenshots/printouts
- Postman-generated API documentation printout
