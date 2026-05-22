export interface FarmAlert {
  alert_type?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface FarmAddress {
  area_name?: string;
  postcode?: string;
  [key: string]: unknown;
}

export interface SensorReading {
  value?: string | number;
  [key: string]: unknown;
}

export interface FarmSensor {
  sensor_id: string;
  type: string;
  status?: boolean;
  readings?: SensorReading[];
  [key: string]: unknown;
}

export interface Farm {
  id?: string;
  _id?: string;
  name?: string;
  farm_name?: string;
  location?: string;
  crop_type?: string;
  owner_id?: string;
  created_at?: string;
  latitude?: number;
  longitude?: number;
  weather?: unknown;
  address?: FarmAddress;
  alerts_history?: FarmAlert[];
  weather_logs?: unknown[];
  sensors?: FarmSensor[];
  [key: string]: unknown;
}
