# Agri Guide

Agri Guide is a final-year smart agriculture web application for managing farms, viewing weather and sensor context, and running AI-assisted crop image scans. The project includes an Angular frontend, a Flask API backend, MongoDB/Cosmos-style persistence, Azure Blob Storage for images, and email verification/password reset support.

## Main Features

- User authentication, email verification, and password reset.
- Farm management with ownership-based access control.
- Weather sync using backend Open-Meteo integration.
- Sensor readings, demo/manual/IoT source labels, and dashboard summaries.
- AI-assisted crop scan workflow with saved scan history and image storage.
- Profile image upload and dashboard health/analytics polish.

## Tech Stack

- Frontend: Angular, TypeScript, Bootstrap, Chart.js, Leaflet.
- Backend: Flask, Python, PyMongo, JWT, bcrypt.
- Database: MongoDB/Cosmos-style document database.
- Storage: Azure Blob Storage.
- Email: Brevo SMTP.
- Hosting: Azure App Service backend and Vercel frontend.

## Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Before running locally, fill `.env` with local development values. Do not commit `.env`.

## Frontend Setup

```bash
cd frontend
npm install
npm start
```

The local frontend expects the API URL configured in `frontend/src/environments/environment.ts`.

## Environment Variables

Backend variables are documented in `backend/.env.example` and should be configured with deployment-safe values outside source control:

- `SECRET_KEY`
- `MONGO_URI`
- `MONGO_DB_NAME`
- `FLASK_ENV`
- `FLASK_HOST`
- `FLASK_PORT`
- `FLASK_DEBUG`
- `FRONTEND_ORIGIN`
- `FRONTEND_VERIFY_EMAIL_URL`
- `FRONTEND_RESET_PASSWORD_URL`
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER_NAME`
- `AI_SCAN_IMAGE_STORAGE_ENABLED`
- `EMAIL_ENABLED`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `EMAIL_FROM`

Keep real MongoDB, Azure, Brevo, and JWT secrets in local environment files or cloud app settings only.

## Tests And Build

Backend tests:

```bash
cd backend
python -m pytest
```

Frontend production build:

```bash
cd frontend
npm run build
```

## AI Limitation

The current custom crop disease model is a prototype-grade V1 integration. It is useful for demonstrating the scan workflow, storage, reporting, and fallback behavior, but it can be unreliable and may over-predict a class. Results should be treated as AI-assisted guidance only, not expert confirmation.

## Submission Note

Do not include local secrets or generated/runtime files in the final source-code zip:

- `.env` files with real values
- `node_modules/`
- `.venv/` or `venv/`
- `dist/`
- `.angular/`
- `.pytest_cache/`
- `__pycache__/`
- training datasets or uploaded image caches
- `kaggle.json`
