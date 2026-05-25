# Agri-Guide Azure Deployment Preparation Plan

Status: Ready for Validation

## Scope

Prepare the existing Agri-Guide Angular + Flask MVP for later Azure deployment without deploying resources or committing secrets.

## Architecture

- Frontend: Angular app in `frontend/`, intended for Azure Static Web Apps.
- Backend: Flask API in `backend/`, intended for Azure Linux App Service.
- Database: MongoDB via `MONGO_URI`, with MongoDB Atlas as the preferred managed option.

## Preparation Tasks

- Add production WSGI startup support for Flask.
- Keep local Flask startup via `python app.py`.
- Support configurable CORS frontend origin while preserving local Angular origins.
- Keep Angular API base URL environment-driven.
- Document Azure setup, environment variables, testing, and rollback.
- Validate with frontend build and backend pytest.

## Decisions

- No Azure resources will be created in this pass.
- No secrets will be committed.
- No routing or feature behavior will be changed.
