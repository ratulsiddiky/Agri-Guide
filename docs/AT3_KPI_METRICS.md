# AT3 KPI Metrics

## Project Overview

Agri-Guide is an Angular and Flask smart agriculture MVP. The frontend runs at `http://localhost:4200` and the backend runs at `http://localhost:5001`.

The Home dashboard connects to six Flask smart agriculture endpoints:

- `GET /api/system/metrics`
- `GET /api/sensors/latest`
- `POST /api/ai/detect`
- `GET /api/irrigation/decision`
- `GET /api/weather/alert`
- `GET /api/sensors/failover-test`

The MVP uses simulated AI and IoT data so the system is reliable for demonstration. The design allows future upgrades to a real CNN crop disease model, ESP32 sensor devices, MongoDB telemetry storage, and cloud deployment.

## KPI Targets

| KPI | Target | Evidence Source |
| --- | --- | --- |
| Backend API latency | Under `500 ms` | `/api/system/metrics` response and browser Network tab |
| Simulated AI response latency | Under `500 ms` | `/api/ai/detect` and Network tab timing |
| Dashboard API availability | All six smart dashboard API calls return HTTP `200` | Browser Network tab |
| Sensor data freshness | Under `60 seconds` | `/api/system/metrics` field `sensor_data_freshness_seconds` |
| Uptime target | `99.9%` target | `/api/system/metrics` field `uptime_percentage_target` |
| Humidity validity | `0%` to `100%` | `/api/sensors/latest` field `humidity_percent` |
| Soil moisture validity | `0%` to `100%` | `/api/sensors/latest` and `/api/irrigation/decision` |
| Sensor failover | Return interpolated readings when sensor is offline | `/api/sensors/failover-test` |

## Data Validity Rules

- `humidity_percent` must be between `0` and `100`.
- `soil_moisture_percent` must be between `0` and `100`.
- `temperature_c` should be a realistic agricultural environment value for the demo.
- `light_lux` should be a positive number.
- `timestamp` values should be returned for time-sensitive API responses.
- When a sensor is offline, the failover endpoint should return:
  - `sensor_status`
  - `failover_mode`
  - `last_valid_reading`
  - `interpolated_reading`
  - `confidence`
  - `alert`

## AT3 MVP Success Criteria

The AT3 MVP is considered successful when:

- The Angular dashboard loads without breaking the existing app.
- The Flask backend exposes the six smart agriculture endpoints.
- The dashboard receives backend values for system health, latest sensors, AI detection, irrigation, weather alert, and failover.
- Static fallback values keep the dashboard usable if an endpoint fails during the demo.
- Backend tests pass.
- Angular production build succeeds.
