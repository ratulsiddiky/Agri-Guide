# AT3 Demo Script

## Demo Length

Target length: 5 to 7 minutes.

Project:

- Name: Agri-Guide
- Type: Angular and Flask smart agriculture MVP
- Frontend: `http://localhost:4200`
- Backend: `http://localhost:5001`

## 1. Introduction

"Hello, my project is Agri-Guide, a smart agriculture MVP built with Angular for the frontend and Flask for the backend.

The aim of the system is to help farmers monitor farm conditions, view sensor-style readings, receive irrigation guidance, see weather alerts, and demonstrate how AI crop detection could be integrated.

For AT3, the system uses simulated AI and IoT data. This keeps the demo reliable, while still showing the structure needed for future real sensor and AI integration."

## 2. Show GitHub Project Structure

"First, I will show the project structure.

The `frontend/` folder contains the Angular application. The Home dashboard is inside the dashboard components folder.

The `backend/` folder contains the Flask API. The main app is `backend/app.py`, and the API routes are organised using Flask blueprints.

The `docs/` folder contains the AT3 evidence, KPI metrics, and this demo script."

Suggested files to show:

- `frontend/src/app/components/dashboard/home/`
- `frontend/src/app/services/api.service.ts`
- `backend/app.py`
- `backend/blueprints/`
- `docs/AT3_KPI_METRICS.md`
- `docs/AT3_TESTING_EVIDENCE.md`

## 3. Run the Backend

"Next, I will start the Flask backend."

Command:

```powershell
cd backend
python app.py
```

"The backend runs on `http://localhost:5001`. It provides the smart agriculture API endpoints used by the dashboard."

## 4. Run the Frontend

"Now I will start the Angular frontend."

Command:

```powershell
cd frontend
npm start
```

"The frontend runs on `http://localhost:4200`."

## 5. Login or Register

"If the app requires authentication, I will register or log in using a demo account.

This shows that the existing authentication flow still works and was not broken by the smart agriculture dashboard changes."

Demo steps:

- Open `http://localhost:4200`.
- Register a new user if needed.
- Log in with the demo user.
- Navigate to the Home dashboard.

## 6. Show the Home Dashboard

"This is the Agri-Guide Home dashboard.

At the top, the dashboard shows a clean Agri Guide overview. The KPI cards show total farms, active alerts, total sensors, average soil moisture, and today's forecast.

Below that, the smart agriculture cards show live-style backend values for system health, sensor readings, irrigation decision, AI crop detection, weather alert, and failover testing."

Point out:

- System Health
- Latest Sensor Readings
- Irrigation Decision
- AI Crop Detection
- Weather Alert
- Failover Test
- Recent sensor readings table

## 7. Show Browser Network Tab

"To prove the dashboard is connected to the backend, I will open the browser Developer Tools and show the Network tab."

Demo steps:

- Open Developer Tools.
- Go to Network.
- Refresh the dashboard.
- Filter by `api`.
- Show that all six requests return HTTP `200`.

Expected API calls:

- `GET /api/system/metrics`
- `GET /api/sensors/latest`
- `POST /api/ai/detect`
- `GET /api/irrigation/decision`
- `GET /api/weather/alert`
- `GET /api/sensors/failover-test`

"This shows the Angular dashboard is receiving data from the Flask backend."

## 8. Show Backend Endpoints Directly

"I can also test the backend endpoints directly using a browser or Postman."

Example endpoints:

- `http://localhost:5001/api/system/metrics`
- `http://localhost:5001/api/sensors/latest`
- `http://localhost:5001/api/irrigation/decision`
- `http://localhost:5001/api/weather/alert`
- `http://localhost:5001/api/sensors/failover-test`

For the AI endpoint, use Postman because it is a POST request:

- `POST http://localhost:5001/api/ai/detect`

"The responses are JSON and include timestamps, status values, predictions, and recommendations."

## 9. Explain Smart Agriculture Features

"The System Health card reports API status, database status, and target latency.

The Latest Sensor Readings card simulates IoT sensor data such as temperature, humidity, soil moisture, and light.

The Irrigation Decision card uses simple rule-based logic. For example, if soil moisture is in an acceptable range, no irrigation is required.

The AI Crop Detection card simulates a crop disease detection model. It returns a label, confidence score, and recommendation. This is not a real model yet, but it demonstrates the planned AI workflow.

The Weather Alert card simulates a farm weather warning.

The Failover Test card demonstrates resilience. If a sensor is offline, the system can return an interpolated reading based on the last valid value."

## 10. Explain Testing Evidence

"For testing evidence, the backend pytest suite passes with 11 tests.

The Angular production build succeeds.

The dashboard API calls are checked in the browser Network tab and should return HTTP 200.

There may be a CSS budget warning during the Angular build, but it is non-blocking because the application still builds successfully."

## 11. Future Upgrade Path

"The current system is an MVP with simulated data, but it has a clear upgrade path.

The simulated AI endpoint can be replaced with a real CNN model, such as MobileNetV2, ResNet50, or EfficientNet.

The simulated sensor readings can be replaced with real ESP32 sensor devices sending temperature, humidity, soil moisture, and light readings.

The backend can store real sensor telemetry in MongoDB.

The project can also be deployed to cloud infrastructure so farmers can access the dashboard from anywhere."

## 12. Closing

"In summary, Agri-Guide demonstrates a working Angular and Flask smart agriculture MVP.

It includes authentication, farm management, a modern dashboard, six smart agriculture API endpoints, simulated AI and IoT data, KPI evidence, and a clear future upgrade path.

Thank you."
