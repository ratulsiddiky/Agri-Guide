# AT3 Testing Evidence

## Summary

This document records the testing evidence for the Agri-Guide AT3 smart agriculture MVP.

Project URLs:

- Frontend: `http://localhost:4200`
- Backend: `http://localhost:5001`

Confirmed results:

- Backend pytest result: `11 passed`
- Angular production build result: successful
- CSS budget warning: non-blocking warning only

## Backend Test Evidence

Backend automated tests were run with pytest.

Result:

```text
11 passed
```

This confirms the existing backend behaviour remains stable after adding the AT3 smart agriculture MVP endpoints.

## Angular Build Evidence

The Angular production build completed successfully.

Result:

```text
Angular production build successful
```

If a CSS budget warning appears, it is treated as non-blocking because the application still compiles and runs. The warning can be addressed later by reducing CSS size or adjusting build budgets.

## API Endpoint Testing Checklist

Test each endpoint using a browser, Postman, curl, or the Angular dashboard Network tab.

| Endpoint | Method | Expected Result | Status |
| --- | --- | --- | --- |
| `/api/system/metrics` | GET | Returns system health, latency, uptime target, and timestamp | Pass |
| `/api/sensors/latest` | GET | Returns simulated temperature, humidity, soil moisture, and light data | Pass |
| `/api/ai/detect` | POST | Returns simulated AI crop detection result and confidence | Pass |
| `/api/irrigation/decision` | GET | Returns rule-based irrigation decision | Pass |
| `/api/weather/alert` | GET | Returns simulated weather alert and recommended action | Pass |
| `/api/sensors/failover-test` | GET | Returns simulated offline sensor failover and interpolated reading | Pass |

## Browser Network Tab Evidence

Manual browser evidence should show all six dashboard API calls returning HTTP `200`.

Checklist:

- Open `http://localhost:4200`.
- Open browser Developer Tools.
- Go to the Network tab.
- Refresh the dashboard page.
- Confirm these requests appear:
  - `GET /api/system/metrics` returns `200`
  - `GET /api/sensors/latest` returns `200`
  - `POST /api/ai/detect` returns `200`
  - `GET /api/irrigation/decision` returns `200`
  - `GET /api/weather/alert` returns `200`
  - `GET /api/sensors/failover-test` returns `200`

## Manual Demo Testing Checklist

- Start the Flask backend on `http://localhost:5001`.
- Start the Angular frontend on `http://localhost:4200`.
- Register or log in if required.
- Open the Home dashboard.
- Confirm the dashboard displays:
  - Total farms KPI
  - System Health card
  - Latest Sensor Readings card
  - Irrigation Decision card
  - AI Crop Detection card
  - Weather Alert card
  - Failover Test card
  - Recent sensor readings table
- Confirm backend values are visible on the dashboard.
- Confirm fallback dashboard values remain available if the backend is stopped.
- Confirm existing login, farms, admin, and farm CRUD flows are not broken.

## Notes

The AT3 MVP uses simulated AI and IoT data. This is intentional for a reliable student demonstration. The system is structured so the simulated data can later be replaced by a real CNN model, ESP32 sensor readings, MongoDB telemetry storage, and cloud-hosted services.
