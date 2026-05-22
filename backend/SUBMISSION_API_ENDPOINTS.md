# SUBMISSION API Endpoints (CW1)

This document summarizes the Flask API endpoints implemented for the SmartAgri Guide backend.

Base URL (local default): `http://127.0.0.1:5001`

## Endpoint Matrix

| Feature | Method | URL | Description | Authentication |
|---|---|---|---|---|
| Health/Home | `GET` | `/` | Basic API availability message. | Public |
| Sign Up | `POST` | `/api/users/signup` | Create account with username, email, password, and preferences. | Public |
| Register (alias) | `POST` | `/api/users/register` | Alias endpoint for signup flow. | Public |
| Verify Email | `GET` | `/api/users/verify?token={token}` | Marks user as verified with verification token. | Public |
| Login | `POST` | `/api/login` | Basic Auth login, returns JWT token and role. | Public |
| Logout | `GET` | `/api/logout` | Invalidates JWT by adding token to blacklist collection. | JWT Required |
| List Users | `GET` | `/api/users` | Returns all users (without passwords). | Admin JWT |
| Get Farms | `GET` | `/api/farms?page={page}&limit={limit}` | Paginated farm retrieval. | Public |
| Get Farm | `GET` | `/api/farms/{farmId}` | Retrieve a single farm by id. | Public |
| Create Farm | `POST` | `/api/farms` | Create a new farm document. | JWT Required |
| Update Farm | `PUT` | `/api/farms/{farmId}` | Update a farm (owner/admin only). | JWT Required |
| Delete Farm | `DELETE` | `/api/farms/{farmId}` | Delete a farm (admin only). | Admin JWT |
| Add Sensor | `POST` | `/api/farms/{farmId}/sensors` | Append sensor sub-document to farm. | JWT Required |
| Search Farms | `GET` | `/api/farms/search?q={term}` | Full-text search over farms collection. | Public |
| Sync Weather | `POST` | `/api/farms/{farmId}/sync_weather` | Pulls external weather API data and stores weather log. | JWT Required |
| Broadcast Alert | `POST` | `/api/farms/alerts/broadcast` | GeoJSON-based emergency alert broadcast to matching farms. | Admin JWT |
| Farm Insights | `GET` | `/api/farms/{farmId}/insights` | Aggregation pipeline for farm-level averages. | JWT Required |
| Irrigation Check | `GET` | `/api/farms/{farmId}/irrigation_check` | Rule-based moisture check from latest sensor reading. | JWT Required |
| Regional Insights | `GET` | `/api/farms/region/{regionName}/insights` | Aggregation pipeline for regional community averages. | Public |

## Notes on REST and CW1 Criteria

- CRUD operations are implemented across user and farm resources.
- Sub-document management is implemented through sensor insertion and weather/alert history updates.
- Responses use appropriate HTTP status codes (`200`, `201`, `400`, `401`, `403`, `404`, `409`, `500`, `502`).
- Authentication uses JWT with blacklist-based logout handling.
- Authorization enforces role and ownership constraints for protected operations.
