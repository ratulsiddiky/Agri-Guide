# Azure Deployment Plan

This plan prepares the Agri-Guide Angular + Flask MVP for later Azure deployment without committing secrets.

## Local Development

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe app.py
```

Frontend:

```powershell
cd frontend
npm install
npm run start
```

Local URLs:

- Frontend: `http://localhost:4200`
- Backend: `http://localhost:5001`
- Local API base URL: `http://127.0.0.1:5001/api`

## Backend: Azure Linux App Service

Recommended target: Azure App Service on Linux running Python.

Deployment preparation:

- Install dependencies from `backend/requirements.txt`.
- Use `backend/startup.sh` as the App Service startup command.
- The startup script runs:

```bash
gunicorn --bind=0.0.0.0:${PORT:-8000} app:app
```

The Flask app exposes `app = create_app()` in `backend/app.py`, so WSGI servers can import `app:app`. Local development still works with `python app.py`.

Required backend App Service settings:

- `SECRET_KEY`: strong random production secret.
- `MONGO_URI`: MongoDB connection string.
- `MONGO_DB_NAME`: production database name.
- `FLASK_ENV`: `production`.
- `FLASK_HOST`: optional for local runs; App Service uses Gunicorn binding.
- `FLASK_PORT`: optional for local runs.
- `FRONTEND_ORIGIN`: deployed frontend origin, for example `https://your-agri-guide-app.azurestaticapps.net`.

Do not store real secrets in source control. Configure production values in Azure App Service application settings.

## Frontend: Azure Static Web Apps

Recommended target: Azure Static Web Apps for the Angular frontend.

Typical settings:

- App location: `frontend`
- Output location: `dist/smart-agri-fe`
- Build command: `npm run build`
- API location: leave empty because the Flask API is hosted separately on App Service.

Before deploying, update the production API placeholder in `frontend/src/environments/environment.prod.ts`:

```ts
apiBaseUrl: 'https://your-agri-guide-api.azurewebsites.net/api'
```

Use the actual App Service URL after the backend is created.

## MongoDB Atlas Option

MongoDB Atlas is a good managed database option for this MVP.

Recommended setup:

- Create a dedicated Atlas cluster and database.
- Create a least-privilege database user for the app.
- Restrict network access where practical.
- Store the Atlas connection string only in the Azure `MONGO_URI` app setting.
- Use a separate database name for production through `MONGO_DB_NAME`.

## Post-Deployment Testing Checklist

- Open the backend root URL and confirm the welcome JSON response.
- Confirm `/api` endpoints respond through the deployed App Service URL.
- Confirm CORS allows the deployed Static Web Apps origin.
- Register or log in through the deployed frontend.
- Confirm protected `/home` behavior still redirects unauthenticated users.
- Confirm dashboard API cards load without browser console CORS errors.
- Create, view, update, and delete a test farm.
- Run backend tests locally before each deployment with `python -m pytest`.
- Run the frontend production build before each deployment with `npm run build`.
- Review Azure App Service logs for startup, MongoDB, and authentication errors.

## Rollback Plan

- Keep the last known-good frontend build or repository revision available.
- If frontend deployment fails, redeploy the previous Static Web Apps build.
- If backend deployment fails, redeploy the previous App Service package or revert to the previous Git revision.
- If configuration causes failure, restore the previous Azure App Service application settings.
- If database migration or data changes are introduced later, take a MongoDB backup before deployment and restore from that backup if needed.
- Verify rollback by repeating the login, protected route, dashboard, and farm CRUD checks.
