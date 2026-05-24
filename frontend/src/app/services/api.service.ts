import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Farm } from '../models/farm.model';

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

  detectCropDisease() {
    return this.http.post<CropDetectionResponse>(`${this.baseUrl}/ai/detect`, {});
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
