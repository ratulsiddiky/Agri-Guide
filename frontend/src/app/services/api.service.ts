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
}
