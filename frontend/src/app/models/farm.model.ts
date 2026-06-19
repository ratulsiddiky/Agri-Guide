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

export type FarmLocationSource =
  | 'browser_geolocation'
  | 'manual_coordinates'
  | 'manual_address'
  | 'approximate_demo_location';

export interface FarmGeoLocation {
  type?: string;
  coordinates?: number[];
  [key: string]: unknown;
}

export interface SensorReading {
  value?: string | number;
  unit?: string;
  timestamp?: string;
  user_id?: string;
  notes?: string;
  source?: string;
  [key: string]: unknown;
}

export interface FarmSensor {
  sensor_id: string;
  type: string;
  farm_id?: string;
  user_id?: string;
  value?: string | number;
  unit?: string;
  status?: boolean | string;
  timestamp?: string;
  source?: string;
  readings?: SensorReading[];
  [key: string]: unknown;
}

export interface Farm {
  id?: string;
  _id?: string;
  name?: string;
  farm_name?: string;
  location?: string | FarmGeoLocation;
  crop_type?: string;
  owner_id?: string;
  created_at?: string;
  latitude?: number;
  longitude?: number;
  location_source?: FarmLocationSource;
  address_line?: string;
  city?: string;
  region?: string;
  postcode?: string;
  country?: string;
  weather?: unknown;
  address?: FarmAddress;
  alerts_history?: FarmAlert[];
  weather_logs?: unknown[];
  sensors?: FarmSensor[];
  [key: string]: unknown;
}
