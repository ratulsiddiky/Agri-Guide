import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Farm, FarmLocationSource, FarmSensor } from '../models/farm.model';

export interface FarmPagination {
  page: number;
  limit: number;
  total: number;
  has_next: boolean;
}

export interface FarmListResponse {
  data: Farm[];
  pagination: FarmPagination;
}

export interface FarmMutationResponse {
  message: string;
  farm_id?: string;
}

export interface BroadcastAlertRequest {
  alert_type: string;
  danger_zone: {
    type: 'Polygon';
    coordinates: number[][][];
  };
}

export interface BroadcastAlertResponse {
  message: string;
  farms_notified: number;
}

export interface RegionalInsightsResponse {
  message: string;
  data: {
    community_avg_temp: number;
    total_farms_included: number;
  };
}

export interface SystemMetricsResponse {
  api_status: string;
  database_status: string;
  backend_latency_ms: number;
  target_latency_ms: number;
  ai_model_mode: string;
  sensor_data_freshness_seconds: number;
  uptime_percentage_target: string;
  timestamp: string;
}

export interface LatestSensorsResponse {
  farm_id: string;
  temperature_c: number;
  humidity_percent: number;
  soil_moisture_percent: number;
  light_lux: number;
  source: string;
  status: string;
  timestamp: string;
}

export interface DashboardSensorRow {
  sensor: string;
  farm: string;
  type: string;
  value: string;
  status: string;
}

export interface DashboardSummaryResponse {
  total_farms: number;
  total_sensors: number;
  average_soil_moisture: number | null;
  latest_temperature: number | null;
  latest_humidity: number | null;
  active_alerts_count: number;
  irrigation_recommendation: string;
  sensor_rows: DashboardSensorRow[];
}

export interface SensorHistoryResponse {
  farm_id: string;
  farm_name: string;
  timestamps: string[];
  series: {
    soil_moisture: Array<number | null>;
    temperature: Array<number | null>;
    humidity: Array<number | null>;
  };
  data_source: 'stored_sensor_readings' | 'simulated_from_latest';
}

export interface FarmWeatherResponse {
  farm_id: string;
  farm_name: string;
  latitude: number;
  longitude: number;
  location_source: FarmLocationSource;
  temperature_c: number | null;
  humidity_percent: number | null;
  wind_speed_kmh: number | null;
  precipitation_mm: number | null;
  rain_mm: number | null;
  weather_code: number | null;
  condition_summary: string;
  timestamp: string;
  provider: 'Open-Meteo';
  data_source: 'open_meteo_current_weather' | 'fallback_simulated_weather';
}

export interface SensorReadingMutationResponse {
  message: string;
  farm_id: string;
  sensor_type: string;
  reading: {
    farm_id: string;
    user_id: string;
    username?: string;
    sensor_type: string;
    value: number;
    unit: string;
    notes?: string | null;
    timestamp: string;
    source: string;
  };
  sensor: FarmSensor;
}

export interface CropDetectionResponse {
  mode: string;
  model_type: string;
  cnn_architecture_plan: {
    baseline: string;
    comparison_models: string[];
    chosen_for_future_upgrade: string;
    reason: string;
  };
  prediction: {
    label: string;
    confidence: number;
    recommendation: string;
  };
  latency_requirement_ms: number;
  timestamp: string;
}

export interface CropScanResponse {
  scan_id: string;
  farm_id?: string | null;
  farm_name?: string | null;
  crop_type?: string | null;
  model_mode: 'simulated_ai';
  model_type: 'crop_leaf_health_classifier';
  future_upgrade_model: string;
  label: string;
  confidence: number;
  severity: string;
  recommendation: string;
  prevention_steps: string[];
  latency_ms: number;
  image_metadata: {
    filename: string;
    content_type?: string | null;
    width?: number | null;
    height?: number | null;
    format?: string | null;
  };
  has_image?: boolean;
  image_endpoint?: string;
  image_url?: string;
  possible_causes?: string[];
  likely_causes?: string[];
  immediate_actions?: string[];
  prevention_plan?: string[];
  monitoring_advice?: string;
  when_to_seek_expert_help?: string;
  explanation?: string;
  confidence_explanation?: string;
  severity_explanation?: string;
  advisory_disclaimer?: string;
  created_at?: string;
  timestamp: string;
}

export interface CropScanListResponse {
  farm_id?: string;
  count: number;
  scans: CropScanResponse[];
}

export interface IrrigationDecisionResponse {
  soil_moisture_percent: number;
  temperature_c: number;
  decision: string;
  recommended_action: string;
  priority: string;
  rule_used: string;
  timestamp: string;
}

export interface WeatherAlertResponse {
  location: string;
  alert_level: string;
  message: string;
  recommended_action: string;
  mode: string;
  timestamp: string;
}

export interface FailoverTestResponse {
  sensor_status: string;
  failover_mode: string;
  logic: string;
  last_valid_reading: {
    sensor_id: string;
    soil_moisture_percent: number;
    timestamp: string;
  };
  interpolated_reading: {
    sensor_id: string;
    soil_moisture_percent: number;
    method: string;
    timestamp: string;
  };
  confidence: string;
  alert: string;
}

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private readonly http: HttpClient) {}

  public getErrorMessage(error: any): string {
    const backendMessage = error?.error?.message;

    if (typeof backendMessage === 'string' && backendMessage.trim()) {
      return backendMessage;
    }

    if (error?.status === 400) {
      return 'The request could not be completed because the farm data was invalid.';
    }

    if (error?.status === 401) {
      return 'You are not signed in or your session has expired. Please log in again.';
    }

    if (error?.status === 403) {
      return 'You do not have permission to perform this farm action.';
    }

    if (error?.status === 404) {
      return 'The requested farm record could not be found.';
    }

    if (error?.status >= 500) {
      return 'The server was unable to complete the farm request. Please try again later.';
    }

    return '';
  }

  getFarms(page = 1, limit = 20) {
    return this.http.get<Farm[] | FarmListResponse>(
      `${this.baseUrl}/farms?page=${page}&limit=${limit}`
    );
  }

  getMyFarms(page = 1, limit = 9) {
    return this.http.get<FarmListResponse>(
      `${this.baseUrl}/farms/my?page=${page}&limit=${limit}`
    );
  }

  getFarmById(id: string) {
    return this.http.get<Farm>(`${this.baseUrl}/farms/${id}`);
  }

  searchFarms(query: string) {
    const params = new HttpParams().set('q', query);
    return this.http.get<{ data: Farm[] }>(
      `${this.baseUrl}/farms/search`,
      { params }
    );
  }

  createFarm(data: Partial<Farm>) {
    return this.http.post<FarmMutationResponse>(`${this.baseUrl}/farms`, data);
  }

  updateFarm(id: string, data: Partial<Farm>) {
    return this.http.put<FarmMutationResponse>(`${this.baseUrl}/farms/${id}`, data);
  }

  deleteFarm(id: string) {
    return this.http.delete<void>(`${this.baseUrl}/farms/${id}`);
  }

  getFarmInsights(id: string) {
    return this.http.get<{ dashboard_data: unknown }>(
      `${this.baseUrl}/farms/${id}/insights`
    );
  }

  checkIrrigation(id: string) {
    return this.http.get<unknown>(`${this.baseUrl}/farms/${id}/irrigation_check`);
  }

  syncWeather(id: string) {
    return this.http.post<void>(`${this.baseUrl}/farms/${id}/sync_weather`, {});
  }

  addSensor(id: string, sensor: { sensor_id: string; type: string }) {
    return this.http.post<void>(`${this.baseUrl}/farms/${id}/sensors`, sensor);
  }

  getFarmSensors(id: string) {
    return this.http.get<{ farm_id: string; count: number; sensors: FarmSensor[] }>(
      `${this.baseUrl}/farms/${id}/sensors`
    );
  }

  generateDemoSensors(id: string) {
    return this.http.post<{ message: string; farm_id: string; count: number; sensors: FarmSensor[] }>(
      `${this.baseUrl}/farms/${id}/sensors/demo`,
      {}
    );
  }

  getSensorHistory(id: string) {
    return this.http.get<SensorHistoryResponse>(`${this.baseUrl}/farms/${id}/sensor-history`);
  }

  getFarmWeather(id: string) {
    return this.http.get<FarmWeatherResponse>(`${this.baseUrl}/farms/${id}/weather`);
  }

  addSensorReading(id: string, payload: { sensor_type: string; value: number; unit: string; notes?: string }) {
    return this.http.post<SensorReadingMutationResponse>(`${this.baseUrl}/farms/${id}/sensors/readings`, payload);
  }

  getFarmActionPlan(id: string) {
    return this.http.get<any>(`${this.baseUrl}/farms/${id}/action-plan`);
  }

  broadcastAlert(payload: BroadcastAlertRequest) {
    return this.http.post<BroadcastAlertResponse>(
      `${this.baseUrl}/farms/alerts/broadcast`,
      payload
    );
  }

  getRegionalInsights(regionName: string) {
    return this.http.get<RegionalInsightsResponse>(
      `${this.baseUrl}/farms/region/${encodeURIComponent(regionName)}/insights`
    );
  }

  getSystemMetrics() {
    return this.http.get<SystemMetricsResponse>(`${this.baseUrl}/system/metrics`);
  }

  getLatestSensors() {
    return this.http.get<LatestSensorsResponse>(`${this.baseUrl}/sensors/latest`);
  }

  getDashboardSummary() {
    return this.http.get<DashboardSummaryResponse>(`${this.baseUrl}/dashboard/summary`);
  }

  detectCropDisease() {
    return this.http.post<CropDetectionResponse>(`${this.baseUrl}/ai/detect`, {});
  }

  scanCropHealth(formData: FormData) {
    return this.http.post<CropScanResponse>(`${this.baseUrl}/ai/crop-scan`, formData);
  }

  getCropScans() {
    return this.http.get<CropScanListResponse>(`${this.baseUrl}/ai/scans`);
  }

  getCropScan(scanId: string) {
    return this.http.get<CropScanResponse>(`${this.baseUrl}/ai/scans/${scanId}`);
  }

  getCropScanImage(scanId: string) {
    return this.http.get(`${this.baseUrl}/ai/scans/${scanId}/image`, {
      responseType: 'blob',
    });
  }

  getFarmCropScans(id: string) {
    return this.http.get<CropScanListResponse>(`${this.baseUrl}/farms/${id}/ai-scans`);
  }

  getIrrigationDecision() {
    return this.http.get<IrrigationDecisionResponse>(`${this.baseUrl}/irrigation/decision`);
  }

  getWeatherAlert() {
    return this.http.get<WeatherAlertResponse>(`${this.baseUrl}/weather/alert`);
  }

  getFailoverTest() {
    return this.http.get<FailoverTestResponse>(`${this.baseUrl}/sensors/failover-test`);
  }
}
