# SUBMISSION API Endpoints (CW2)

This document lists all backend API endpoints called by the Angular frontend (`smart-agri-fe`).

Base URL is configured in `src/environments/environment.ts` as `apiBaseUrl` (currently `http://127.0.0.1:5001/api`).

## Endpoint Matrix

| Feature | Method | URL | Description | Role Required |
|---|---|---|---|---|
| Login | `POST` | `/api/login` | Authenticates user via Basic Auth and returns JWT token/session data. | Public |
| Register | `POST` | `/api/users/register` | Creates user account and starts email verification flow. | Public |
| Logout | `GET` | `/api/logout` | Invalidates current JWT by blacklisting token. | Authenticated |
| Get Farms | `GET` | `/api/farms?page={page}&limit={limit}` | Retrieves paginated farm list for listing/dashboard views. | Public |
| Get Farm Detail | `GET` | `/api/farms/{farmId}` | Retrieves single farm details for farm dashboard page. | Public |
| Search Farms | `GET` | `/api/farms/search?q={query}` | Performs full-text farm search from search and list pages. | Public |
| Create Farm | `POST` | `/api/farms` | Creates a new farm record from farm form (create mode). | Authenticated |
| Update Farm | `PUT` | `/api/farms/{farmId}` | Updates an existing farm from farm form (edit mode). | Owner or Admin |
| Delete Farm | `DELETE` | `/api/farms/{farmId}` | Deletes farm from farms list action. | Admin |
| Add Sensor | `POST` | `/api/farms/{farmId}/sensors` | Adds sensor to farm from farm detail page. | Owner or Admin |
| Farm Insights | `GET` | `/api/farms/{farmId}/insights` | Loads average weather metrics for farm detail intelligence card. | Owner or Admin |
| Irrigation Check | `GET` | `/api/farms/{farmId}/irrigation_check` | Computes irrigation status from latest soil moisture reading. | Owner or Admin |
| Sync Weather | `POST` | `/api/farms/{farmId}/sync_weather` | Pulls external weather data and appends weather log to farm record. | Owner or Admin |
| Broadcast Alert | `POST` | `/api/farms/alerts/broadcast` | Admin broadcasts emergency alert to farms inside GeoJSON polygon. | Admin |
| Regional Insights | `GET` | `/api/farms/region/{regionName}/insights` | Returns community averages for farms in a specific region. | Public |

## Advanced Logic Beyond CW1

### Sync Weather (`POST /api/farms/{farmId}/sync_weather`)
- Uses external Open-Meteo API integration.
- Converts geolocation coordinates into live weather pull.
- Persists weather logs for later analytics and intelligence cards.

### Regional Insights (`GET /api/farms/region/{regionName}/insights`)
- Uses aggregation pipeline logic to compute community averages.
- Produces derived metrics (`community_avg_temp`, `total_farms_included`) rather than raw CRUD data.
- Demonstrates analytics-oriented backend capability beyond baseline CW1 CRUD usage.

## Notes for Submission

- This endpoint list aligns with the CW2 requirement to document all APIs used by the frontend.
- Where access control applies, frontend route guards and interceptor-based JWT forwarding are implemented.
- Admin-only features (`Broadcast Alert`, `Delete Farm`) are protected by role checks on both frontend and backend.
